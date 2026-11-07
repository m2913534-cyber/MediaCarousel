"""Media library rows: thumbnail, name, type/duration and a live progress fill on the playing row."""
import os
from collections import deque
from pathlib import Path
from PySide6.QtCore import Qt,QObject,QTimer,QSize,QRectF,QUrl,Signal
from PySide6.QtGui import QPixmap,QImage,QImageReader,QPainter,QColor,QFont,QPen
from PySide6.QtWidgets import QStyledItemDelegate,QStyle
from model import is_pdf,is_powerpoint,is_still,holds,media_name,clip_bounds,is_virtual,is_lan

THUMB=QSize(192,108)  # drawn at 96×54, stored at 2× for Retina
ROW_HEIGHT=66

def fit_image(image):
    if image.isNull():return QPixmap()
    return QPixmap.fromImage(image.scaled(THUMB,Qt.KeepAspectRatio,Qt.SmoothTransformation))

def label_pixmap(text,background,foreground='#ffffff'):
    pix=QPixmap(THUMB);pix.fill(QColor(background));p=QPainter(pix);p.setPen(QColor(foreground))
    font=QFont();font.setPixelSize(30);font.setBold(True);p.setFont(font);p.drawText(pix.rect(),Qt.AlignCenter,text);p.end();return pix

class ThumbnailCache(QObject):
    """Builds thumbnails one at a time in the background so the list never blocks."""
    updated=Signal()
    def __init__(self,parent=None):
        super().__init__(parent);self.pixmaps={};self.durations={};self.queue=deque();self.queued=set();self.player=None;self.busy=None
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.next)
        self.video_timeout=QTimer(self);self.video_timeout.setSingleShot(True);self.video_timeout.timeout.connect(lambda:self.finish_video(QPixmap()))
    def key(self,item):
        path=item.get('path','')
        try:stamp=os.path.getmtime(path)
        except OSError:stamp=0
        return (path,stamp)
    def get(self,item):
        if item.get('kind')=='black':return self.static('black',lambda:label_pixmap('',  '#000000'))
        if is_lan(item):return self.static('lan',lambda:label_pixmap('LAN','#1f6f63'))
        if is_powerpoint(item):return self.static('ppt',lambda:label_pixmap('PPT','#c4512f'))
        key=self.key(item)
        if key in self.pixmaps:return self.pixmaps[key]
        if key not in self.queued and Path(key[0]).is_file():self.queued.add(key);self.queue.append((key,item));self.timer.start(0)
        return None
    def duration(self,item):return self.durations.get(self.key(item))
    def static(self,name,make):
        if name not in self.pixmaps:self.pixmaps[name]=make()
        return self.pixmaps[name]
    def next(self):
        if self.busy or not self.queue:return
        key,item=self.queue.popleft();path=key[0]
        try:
            if is_pdf(item):self.store(key,self.pdf(path))
            elif is_still(item):self.store(key,self.image(path))
            else:self.video(key,path);return
        except Exception:self.store(key,QPixmap())
        self.timer.start(0)
    def store(self,key,pixmap):
        self.pixmaps[key]=pixmap if not pixmap.isNull() else label_pixmap('?','#3a4250');self.updated.emit()
    def image(self,path):
        reader=QImageReader(path);reader.setAutoTransform(True);size=reader.size()
        if size.isValid():reader.setScaledSize(size.scaled(THUMB,Qt.KeepAspectRatio))
        return fit_image(reader.read())
    def pdf(self,path):
        from PySide6.QtPdf import QPdfDocument
        doc=QPdfDocument(self);doc.load(path)
        try:
            if doc.pageCount()<1:return QPixmap()
            page=doc.pagePointSize(0);size=page.toSize().scaled(THUMB,Qt.KeepAspectRatio) if page.isValid() else THUMB
            return fit_image(doc.render(0,size))
        finally:doc.close();doc.deleteLater()
    def video(self,key,path):
        from PySide6.QtMultimedia import QMediaPlayer,QVideoSink
        if self.player is None:
            # No audio output is attached, so thumbnailing is silent.
            self.player=QMediaPlayer(self);self.sink=QVideoSink(self);self.player.setVideoSink(self.sink)
            self.sink.videoFrameChanged.connect(self.video_frame);self.player.mediaStatusChanged.connect(self.video_status);self.player.errorOccurred.connect(lambda *_:self.finish_video(QPixmap()))
        self.busy=key;self.seeked=False;self.video_timeout.start(6000);self.player.setSource(QUrl.fromLocalFile(path))
    def video_status(self,status):
        from PySide6.QtMultimedia import QMediaPlayer
        if self.busy and status==QMediaPlayer.LoadedMedia:
            duration=self.player.duration();self.durations[self.busy]=duration/1000 if duration>0 else None
            self.player.setPosition(min(1000,max(0,duration//10)));self.seeked=True;self.player.play()
    def video_frame(self,frame):
        if self.busy and self.seeked and frame.isValid():self.finish_video(fit_image(frame.toImage()))
    def finish_video(self,pixmap):
        if not self.busy:return
        key=self.busy;self.busy=None;self.video_timeout.stop()
        if self.player:self.player.stop();self.player.setSource(QUrl())
        self.store(key,pixmap);self.timer.start(0)

class MediaDelegate(QStyledItemDelegate):
    def __init__(self,host):
        super().__init__(host.files);self.host=host
    def palette(self):
        from interface import PALETTES
        return PALETTES[getattr(self.host.interface,'theme_index',0)]
    def sizeHint(self,option,index):return QSize(option.rect.width(),ROW_HEIGHT)
    def paint(self,p,option,index):
        h=self.host;group=h.group_index();items=h.lists[group]['items'] if 0<=group<len(h.lists) else [];row=index.row()
        if not 0<=row<len(items):return
        item=items[row];c=self.palette();r=option.rect;selected=bool(option.state&QStyle.State_Selected)
        p.save();p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(r,QColor(c['raised'] if selected else c['panel']))
        progress=h.row_progress(group,row)
        if progress is not None:
            fill=QColor(c['accent']);fill.setAlpha(46);p.fillRect(QRectF(r.x(),r.y(),r.width()*progress,r.height()),fill)
            p.fillRect(QRectF(r.x(),r.bottom()-2,r.width()*progress,3),QColor(c['accent']))
        if selected or progress is not None:p.fillRect(QRectF(r.x(),r.y(),3,r.height()),QColor(c['accent']))
        p.setPen(QPen(QColor(c['line'])));p.drawLine(r.bottomLeft(),r.bottomRight())
        thumb=QRectF(r.x()+10,r.y()+6,96,54);p.fillRect(thumb,QColor('#000000'))
        pix=h.thumbnails.get(item)
        if pix is not None and not pix.isNull():
            size=pix.size().scaled(thumb.size().toSize(),Qt.KeepAspectRatio);target=QRectF(0,0,size.width(),size.height());target.moveCenter(thumb.center());p.drawPixmap(target,pix,QRectF(pix.rect()))
        missing=not is_virtual(item) and not Path(item.get('path','')).is_file()
        text_x=thumb.right()+10;width=max(10,r.right()-text_x-8)
        font=QFont(option.font);font.setBold(True);p.setFont(font);p.setPen(QColor(c['text']))
        name=('▶ ' if progress is not None else '')+media_name(item)
        p.drawText(QRectF(text_x,r.y()+9,width,22),Qt.AlignLeft|Qt.AlignVCenter,p.fontMetrics().elidedText(name,Qt.ElideMiddle,int(width)))
        font.setBold(False)
        # Themes may size fonts in pixels (pointSize is then -1); shrink whichever is set.
        if option.font.pixelSize()>0:font.setPixelSize(max(11,round(option.font.pixelSize()*.9)))
        else:font.setPointSizeF(max(10,option.font.pointSizeF()*.9))
        p.setFont(font)
        p.setPen(QColor('#e5626e') if missing else QColor(c['dim']))
        p.drawText(QRectF(text_x,r.y()+33,width,20),Qt.AlignLeft|Qt.AlignVCenter,p.fontMetrics().elidedText(self.subtitle(item,missing),Qt.ElideRight,int(width)))
        p.restore()
    def subtitle(self,item,missing):
        if is_lan(item):return self.lan_subtitle(item)
        kind='PDF' if is_pdf(item) else 'PowerPoint' if is_powerpoint(item) else '黑畫面' if item.get('kind')=='black' else '圖片' if is_still(item) else '影片'
        if missing:return '⚠ 檔案遺失 · '+kind
        if holds(item):return kind+' · 手動切換'
        if is_still(item) or is_pdf(item):return f"{kind} · {item.get('seconds',5):g} 秒"
        if kind=='影片':
            length=self.host.thumbnails.duration(item)
            start=item.get('start',0) or 0;end=item.get('end',0) or length
            if length:
                span=max(0,(end or length)-start);return f'{kind} · {int(span)//60:02d}:{int(span)%60:02d}'+(' · 片段' if start or item.get('end') else '')
        return kind

    def lan_subtitle(self,item):
        import lan_receiver
        hub=getattr(self.host,'lan_hub',None)
        if not hub or not hub.running:return '內網畫面 · 接收未啟動'
        key=lan_receiver.item_key(item);info=next((s for s in hub.senders() if s['key']==key),None)
        if not info:return '內網畫面 · 等待來源連線'
        if info['transport']!='tcp':return '內網畫面 · 請在 Sender 改選 TCP 相容'
        if not info['live']:return '內網畫面 · 已連線，等待畫面'
        return f"內網畫面 · {info['fps']:.0f} FPS · {info['width']}×{info['height']}"

def attach(host):
    """Install thumbnails and progress rows on the host's media list."""
    host.thumbnails=ThumbnailCache(host);host.files.setItemDelegate(MediaDelegate(host));host.files.setUniformItemSizes(True)
    host.thumbnails.updated.connect(host.files.viewport().update)
    timer=QTimer(host);host.progress_timer=timer;state={'busy':False}
    def tick():
        busy=host.running or any(l.running for l in host.compositor.layers)
        if busy or state['busy']:host.files.viewport().update()
        state['busy']=busy
    timer.timeout.connect(tick);timer.start(150)

def row_progress(host,group,row):
    """0–1 progress of the item at (group,row) while it is on air, else None."""
    key=(group,row)
    if host.compositor.enabled:
        best=None
        for layer in host.compositor.layers:
            if layer.c.get('kind','playlist')!='playlist' or 'items' in layer.c or layer.current!=key:continue
            d=layer.decks[layer.active];best=max(best or 0,deck_fraction(d,layer.elapsed))
        return best
    if host.current!=key or host.cue_item is not None:return None
    return deck_fraction(host.decks[host.active],host.elapsed)

def deck_fraction(deck,elapsed):
    if deck.kind=='video':
        start,end=clip_bounds(deck.config,deck.player.duration());span=end-start
        return max(0.,min(1.,(deck.player.position()-start)/span)) if span>0 else 0.
    if deck.kind=='pdf' or holds(deck.config):return 1.
    seconds=deck.config.get('seconds',5) or 5
    return max(0.,min(1.,elapsed/seconds))
