"""LAN projection: a simulated LEDSpace Sender 1.5.4 (TCP mode) pairs, streams JPEGs, and shows in single and multi-screen."""
import os,time,tempfile,json,uuid
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ['MEDIACAROUSEL_SESSION_DIR']=tempfile.mkdtemp()
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from PySide6.QtCore import QBuffer,QByteArray,QIODevice
from PySide6.QtGui import QImage,QColor
from app import QApplication,Window
from model import save_project,load_project
import lan_panel

def pump(seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)

def jpeg(color,size=(640,360)):
    image=QImage(*size,QImage.Format_RGB32);image.fill(QColor(color));data=QByteArray();buf=QBuffer(data);buf.open(QIODevice.WriteOnly);image.save(buf,'JPG',75);return bytes(data)

class Sender:
    """Same requests, headers and bodies as LEDSpace Sender 1.5.4 lan-common.js / lan-tcp.js."""
    def __init__(self,base,code,name='舞台左電腦',key=None):self.base=base;self.code=code;self.name=name;self.key=key or str(uuid.uuid4());self.id=None
    def call(self,path,body=None,data=None,ctype=None):
        headers={'X-LEDSpace-Code':self.code}
        if body is not None:data=json.dumps(body).encode();ctype='application/json'
        if ctype:headers['Content-Type']=ctype
        req=Request(self.base+path,data=data,headers=headers,method='POST' if data is not None else 'GET')
        try:
            with urlopen(req,timeout=5) as r:return r.status,json.loads(r.read() or b'{}')
        except HTTPError as e:return e.code,json.loads(e.read() or b'{}')
    def connect(self,transport='tcp'):
        assert self.call('/peers')[0]==200
        status,data=self.call('/register',{'name':self.name,'transport':transport,'senderKey':self.key});assert status==200,data;self.id=data['id']
    def frame(self,color,fps=30):return self.call(f'/frame-binary?id={self.id}&fps={fps}',data=jpeg(color),ctype='image/jpeg')
    def leave(self):return self.call('/leave',{'id':self.id})

app=QApplication([]);w=Window();w.session_ready=False;w.session_timer.stop();w.resize(1280,800);w.show()
hub=w.lan_hub;port=hub.start(port=0);base=f'http://127.0.0.1:{port}'
try:
    # Pairing: wrong code rejected; WebRTC senders are told to switch to TCP.
    assert Sender(base,'wrong').call('/peers')[0]==401
    rtc=Sender(base,hub.code,'WebRTC 電腦');rtc.connect('webrtc')
    assert rtc.call('/signal',{'id':rtc.id,'to':'x','data':{}})[0]==404
    assert rtc.frame('red')[0]==403
    rtc.leave()

    s=Sender(base,hub.code);s.connect()
    status,reply=s.frame('red');assert status==200 and reply.get('ok'),reply
    assert s.call(f'/frame-binary?id={s.id}&fps=30',data=b'not a jpeg',ctype='image/jpeg')[0]==400
    pump(.2);info=[x for x in hub.senders() if x['name']=='舞台左電腦'][0]
    assert info['transport']=='tcp' and info['live'] and (info['width'],info['height'])==(640,360)

    # The panel lists the computer and adds it to the current list.
    lan_panel.open_panel(w);panel=w.lan_panel;panel.refresh()
    assert panel.code.text()==hub.code and panel.list.count()==1 and '舞台左電腦' in panel.list.item(0).text()
    w.compositor.enable.setChecked(False);w.lists=[{'name':'現場','items':[]}];w.refresh_groups()
    panel.list.setCurrentRow(0);panel.add();item=w.lists[0]['items'][0]
    assert item['kind']=='lan' and item['lan_key']==s.key and w.files.count()==1

    # Single screen shows the stream live and stays on it (live sources wait for manual advance).
    w.effect.setCurrentText('直接切換');w.files.setCurrentRow(0);w.play_selected();pump(.4)
    d=w.decks[w.active];assert d.kind=='image'
    center=lambda deck:deck.image.pixmap().toImage().pixelColor(deck.image.pixmap().width()//2,deck.image.pixmap().height()//2)
    assert center(d).red()>200 and center(d).blue()<60,center(d).name()
    s.frame('blue');pump(.3);assert center(d).blue()>200,center(d).name()
    pump(6.0);assert w.current==(0,0) and center(d).blue()>200  # signal gone stale: last frame stays
    w.stop()

    # Reconnecting with the same Sender key feeds the same source.
    s2=Sender(base,hub.code,key=s.key);s2.connect();s2.frame('green')
    assert len([x for x in hub.senders() if x['key']==s.key])==1

    # Multi-screen tile from the same list.
    c=w.compositor;c.restore([{'name':'LAN','group':0,'w':960,'h':540}]);c.enable.setChecked(True);c.toggle();pump(.5)
    l=c.layers[0];ld=l.decks[l.active];assert l.current==(0,0) and center(ld).green()>100,center(ld).name()
    c.toggle();c.enable.setChecked(False)

    # Saved projects keep the LAN source as is (no file path rewriting).
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/'lan.mcarousel';save_project(path,w.lists,w.settings());data=load_project(path)
        assert data['lists'][0]['items'][0]['path']=='lan:'+s.key

    s2.leave();pump(.2);assert not [x for x in hub.senders() if x['key']==s.key]
finally:
    hub.stop()
assert not hub.running
print('PASS: LEDSpace Sender pairing (code, TCP/WebRTC), binary JPEG frames, panel add, single/multi live display, hold last frame, reconnect, project save')
w.close();app.processEvents()
