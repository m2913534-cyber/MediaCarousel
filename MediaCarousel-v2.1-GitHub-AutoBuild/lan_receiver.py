"""LAN projection receiver compatible with LEDSpace Sender (TCP compatible mode).

Mirrors LEDSpace 1.2.3 lan-hub.cjs: HTTP on port 49731, X-LEDSpace-Code pairing header,
/register, /peers, /frame-binary (and legacy /frame), /poll, /signal, /leave.
Senders keep only their latest JPEG; frames are decoded on the network thread.
"""
import base64,hmac,json,re,secrets,threading,time,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
from PySide6.QtCore import QObject,Signal
from PySide6.QtGui import QImage

DEFAULT_PORT=49731
MAX_SENDERS=32
PEER_TTL=15.0        # seconds without contact before a sender is dropped
FRAME_STALE=5.0      # a frame older than this counts as "no signal"
MAX_FRAME=2_800_000
FPS_CHOICES=(15,25,30,50,60)
KEY_RE=re.compile(r'^[a-f0-9-]{36}$',re.I)

class Source:
    """One sending computer, identified across reconnects by its Sender key (or name)."""
    def __init__(self,key,name,transport):
        self.key=key;self.name=name;self.transport=transport;self.image=None;self.seq=0;self.at=0.;self.seen=time.monotonic()
        self.width=0;self.height=0;self.target_fps=30;self.fps=0.;self._count=0;self._window=time.monotonic()
    def snapshot(self):
        now=time.monotonic()
        return {'key':self.key,'name':self.name,'transport':self.transport,'fps':self.fps if now-self.at<2 else 0.,
                'width':self.width,'height':self.height,'target_fps':self.target_fps,
                'live':self.image is not None and now-self.at<FRAME_STALE,'seq':self.seq}

class LanHub(QObject):
    changed=Signal()  # senders joined/left or a stream started/stopped
    def __init__(self,parent=None):
        super().__init__(parent);self.lock=threading.Lock();self.server=None;self.thread=None
        self.code='';self.port=0;self.peers={};self.sources={}
    # ---- lifecycle -------------------------------------------------------------------------
    @property
    def running(self):return self.server is not None
    def start(self,port=DEFAULT_PORT,host='0.0.0.0'):
        if self.server:return self.port
        hub=self
        class Handler(LanHandler):pass
        Handler.hub=hub
        last=None
        for candidate in ([port] if port==0 else [port+i for i in range(10)]):
            try:self.server=ThreadingHTTPServer((host,candidate),Handler);break
            except OSError as e:last=e
        if not self.server:raise OSError(f'無法開啟內網接收埠：{last}')
        self.server.daemon_threads=True;self.port=self.server.server_address[1];self.code=secrets.token_hex(6)
        with self.lock:self.peers.clear()
        self.thread=threading.Thread(target=self.server.serve_forever,name='LanHub',daemon=True);self.thread.start()
        self.changed.emit();return self.port
    def stop(self):
        server,self.server=self.server,None
        if server:server.shutdown();server.server_close()
        with self.lock:self.peers.clear()
        self.changed.emit()
    def addresses(self):
        from PySide6.QtNetwork import QNetworkInterface,QAbstractSocket
        result=[]
        for iface in QNetworkInterface.allInterfaces():
            flags=iface.flags()
            if not flags&QNetworkInterface.IsUp or flags&QNetworkInterface.IsLoopBack:continue
            for entry in iface.addressEntries():
                ip=entry.ip()
                if ip.protocol()==QAbstractSocket.IPv4Protocol and not ip.isLoopback():result.append(f'http://{ip.toString()}:{self.port}')
        return result
    # ---- read side (GUI thread) ------------------------------------------------------------
    def senders(self):
        with self.lock:
            self.expire()
            return [s.snapshot() for s in self.sources.values() if any(p.get('key')==s.key for p in self.peers.values())]
    def frame(self,key):
        """(seq, QImage or None, live) for a source key."""
        with self.lock:
            s=self.sources.get(key)
            if not s:return 0,None,False
            return s.seq,s.image,s.image is not None and time.monotonic()-s.at<FRAME_STALE
    def known(self,key):
        with self.lock:return key in self.sources
    def expire(self):
        now=time.monotonic();gone=[pid for pid,p in self.peers.items() if now-p['seen']>PEER_TTL]
        for pid in gone:del self.peers[pid]
        return bool(gone)
    # ---- write side (network threads) ------------------------------------------------------
    def register(self,body):
        with self.lock:
            self.expire()
            if len(self.peers)>=MAX_SENDERS:return 429,{'error':f'已配對來源數達上限（{MAX_SENDERS}）'}
            name=str(body.get('name') or '來源電腦')[:80];transport='tcp' if body.get('transport')=='tcp' else 'webrtc'
            sender_key=body.get('senderKey') if isinstance(body.get('senderKey'),str) and KEY_RE.match(body.get('senderKey')) else None
            key=sender_key or 'name:'+name
            # A reconnecting Sender replaces its previous session but keeps the same source.
            for pid in [pid for pid,p in self.peers.items() if p['key']==key]:del self.peers[pid]
            pid=str(uuid.uuid4());self.peers[pid]={'key':key,'seen':time.monotonic()}
            source=self.sources.get(key)
            if source is None:source=self.sources[key]=Source(key,name,transport)
            source.name=name;source.transport=transport;source.seen=time.monotonic()
        self.changed.emit();return 200,{'id':pid}
    def touch(self,pid):
        with self.lock:
            peer=self.peers.get(pid)
            if not peer:return None
            peer['seen']=time.monotonic();return self.sources.get(peer['key'])
    def leave(self,pid):
        with self.lock:self.peers.pop(pid,None)
        self.changed.emit()
    def put_frame(self,source,jpeg,fps):
        if source.transport!='tcp':return 403,{'error':'非相容模式來源'}
        if len(jpeg)<4 or len(jpeg)>MAX_FRAME or jpeg[:2]!=b'\xff\xd8' or jpeg[-2:]!=b'\xff\xd9':return 400,{'error':'無效影格'}
        if time.monotonic()-source.at<0.008:return 200,{'ok':True,'dropped':True}
        image=QImage.fromData(jpeg,'JPG')
        if image.isNull():return 400,{'error':'無效影格'}
        first=False
        with self.lock:
            now=time.monotonic();first=source.image is None or now-source.at>=FRAME_STALE
            source.image=image;source.seq+=1;source.at=now;source.width=image.width();source.height=image.height()
            source.target_fps=fps if fps in FPS_CHOICES else 30;source._count+=1
            if now-source._window>=1:source.fps=source._count/(now-source._window);source._count=0;source._window=now
        if first:self.changed.emit()
        return 200,{'ok':True}

class LanHandler(BaseHTTPRequestHandler):
    hub=None
    protocol_version='HTTP/1.1'
    def log_message(self,*_):pass
    def headers_out(self):
        self.send_header('Access-Control-Allow-Origin','*');self.send_header('Access-Control-Allow-Headers','Content-Type, X-LEDSpace-Code')
        self.send_header('Access-Control-Expose-Headers','X-LEDSpace-Seq, X-LEDSpace-Fps');self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
        self.send_header('Cache-Control','no-store')
    def reply(self,status,value):
        data=json.dumps(value,ensure_ascii=False).encode()
        self.send_response(status);self.headers_out();self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_OPTIONS(self):
        self.send_response(204);self.headers_out();self.send_header('Content-Length','0');self.end_headers()
    def do_GET(self):self.handle_request(False)
    def do_POST(self):self.handle_request(True)
    def handle_request(self,post):
        hub=self.hub;url=urlparse(self.path);path=url.path;query=parse_qs(url.query)
        try:
            length=int(self.headers.get('Content-Length') or 0)
            limit=3*1024*1024 if path in ('/frame','/frame-binary') else 131072
            if length>limit:
                self.close_connection=True;return self.reply(413,{'error':'訊息太大'})
            raw=self.rfile.read(length) if post and length else b''
            code=self.headers.get('X-LEDSpace-Code') or ''
            if not hub.code or not hmac.compare_digest(code.encode(),hub.code.encode()):return self.reply(401,{'error':'配對碼不正確'})
            body={} if path=='/frame-binary' or not raw else json.loads(raw.decode() or '{}')
            if path=='/register' and post:return self.reply(*hub.register(body))
            if path=='/peers':return self.reply(200,{'peers':[{'id':s['key'],'name':s['name'],'transport':s['transport']} for s in hub.senders()]})
            pid=(body.get('id') if isinstance(body,dict) else None) or (query.get('id') or [None])[0]
            source=hub.touch(pid)
            if source is None:return self.reply(404,{'error':'連線已失效，請重新配對'})
            if path=='/frame-binary' and post:
                if not (self.headers.get('Content-Type') or '').startswith('image/jpeg'):return self.reply(400,{'error':'無效影格'})
                fps=int((query.get('fps') or ['30'])[0]) if (query.get('fps') or ['x'])[0].isdigit() else 30
                return self.reply(*hub.put_frame(source,raw,fps))
            if path=='/frame' and post:
                jpeg=body.get('jpeg')
                if not isinstance(jpeg,str) or len(jpeg)>MAX_FRAME or not jpeg.startswith('data:image/jpeg;base64,'):return self.reply(400,{'error':'無效影格'})
                fps=int(body.get('fps')) if str(body.get('fps','')).isdigit() else 30
                return self.reply(*hub.put_frame(source,base64.b64decode(jpeg.split(',',1)[1],validate=True),fps))
            if path=='/poll':return self.reply(200,{'messages':[]})
            if path=='/signal' and post:return self.reply(404,{'error':'此接收端只支援 TCP 相容模式，請在 Sender 改選 TCP'})
            if path=='/leave' and post:hub.leave(pid);return self.reply(200,{'ok':True})
            return self.reply(404,{'error':'Not found'})
        except Exception:
            try:self.reply(400,{'error':'無效請求'})
            except Exception:pass

def item_key(item):return item.get('lan_key') or item.get('path','')[4:]

def placeholder(text='等待內網訊號'):
    from PySide6.QtGui import QPixmap,QPainter,QColor,QFont
    from PySide6.QtCore import Qt
    pix=QPixmap(1920,1080);pix.fill(QColor('#0b0f14'));p=QPainter(pix);p.setPen(QColor('#65dfc6'))
    font=QFont();font.setPixelSize(64);font.setBold(True);p.setFont(font);p.drawText(pix.rect(),Qt.AlignCenter,text);p.end();return pix

def show_frame(deck,hub,initial=False):
    """Put the newest frame of a LAN source on a deck's image item. Returns True when it changed."""
    from PySide6.QtGui import QPixmap
    key=item_key(deck.config);seq,image,live=hub.frame(key) if hub else (0,None,False)
    if image is None:
        if initial or getattr(deck,'lan_seq',None)!=-1:
            deck.image.setPixmap(placeholder('等待內網訊號' if hub and hub.running else '內網接收未啟動'));deck.lan_seq=-1;return True
        return False
    if seq==getattr(deck,'lan_seq',None):return False   # keep the last frame on screen when the signal drops
    deck.image.setPixmap(QPixmap.fromImage(image));deck.lan_seq=seq;return True
