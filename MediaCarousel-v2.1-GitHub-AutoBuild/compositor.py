"""Native Qt compositor: independent dual media decks and explicitly enabled capture."""
import time, random
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QSizeF, QUrl, QRectF
from PySide6.QtGui import QPen, QColor, QBrush, QPixmap, QImageReader,QTransform
from PySide6.QtWidgets import (QGraphicsRectItem,QGraphicsItem,QGraphicsSimpleTextItem,
    QDockWidget,QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QListWidget,QComboBox,
    QLabel,QDoubleSpinBox,QCheckBox,QInputDialog,QMessageBox,QFileDialog,QScrollArea,QGroupBox,QTabWidget)
from PySide6.QtMultimedia import (QMediaPlayer,QAudioOutput,QMediaCaptureSession,
    QCamera,QMediaDevices,QScreenCapture,QWindowCapture)
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from model import IMAGE_EXT,EFFECTS,following,clip_bounds,normalize_layer,MAX_LAYERS,is_still,media_name,is_pdf,is_powerpoint

def clean_view(widget):
    return widget is not None and bool(widget.property('clean_output'))

class EditorLabel(QGraphicsSimpleTextItem):
    def paint(self,painter,option,widget=None):
        if not clean_view(widget):super().paint(painter,option,widget)

class Handle(QGraphicsRectItem):
    def paint(self,painter,option,widget=None):
        if not clean_view(widget):super().paint(painter,option,widget)
    def __init__(self,parent):
        super().__init__(0,0,22,22,parent);self.setBrush(QColor('#6ee7d4'));self.setPen(QPen(Qt.NoPen));self.setZValue(10000)
        self.setCursor(Qt.SizeFDiagCursor)
    def mousePressEvent(self,e):
        self.origin=e.scenePos();p=self.parentItem();self.size=(p.c['w'],p.c['h']);e.accept()
    def mouseReleaseEvent(self,e):
        self.parentItem().panel.host.persist_session();e.accept()
    def mouseMoveEvent(self,e):
        p=self.parentItem();delta=e.scenePos()-self.origin
        p.resize_to(min(p.panel.width_px-p.pos().x(),max(80,self.size[0]+delta.x())),min(p.panel.height_px-p.pos().y(),max(45,self.size[1]+delta.y())))
        p.panel.sync_controls();e.accept()

class MediaDeck:
    def __init__(self,layer):
        self.layer=layer;self.video=QGraphicsVideoItem(layer);
        from PySide6.QtWidgets import QGraphicsPixmapItem
        from pdf_source import PdfSource
        self.pdf_source=PdfSource();self.pdf_source.ready.connect(self.pdf_ready);self.pdf_source.failed.connect(layer.error)
        self.image=QGraphicsPixmapItem(layer);self.image.setTransformationMode(Qt.SmoothTransformation)
        self.player=QMediaPlayer();
        from audio_meter import AudioProbe
        self.probe=AudioProbe(self.player);self.audio=QAudioOutput();self.player.setAudioOutput(self.audio);self.player.setVideoOutput(self.video)
        self.last_frame=None;self.kind='image';self.item=self.image;self.config={};self.ready=False;self.loaded=False
        self.player.mediaStatusChanged.connect(self.status)
        self.player.errorOccurred.connect(lambda e,m:layer.error(m))
        self.video.videoSink().videoFrameChanged.connect(self.frame)
        self.clear()
    def pdf_ready(self,image,page,total):
        self.image.setPixmap(QPixmap.fromImage(image));self.config['pdf_page']=page;self.ready=True;self.layout()
        if self.layer.current and self is self.layer.decks[self.layer.active]:
            self.layer.source_items()[self.layer.current[1]]['pdf_page']=page;self.layer.elapsed=0
    def clear(self):
        self.pdf_source.close();self.last_frame=None;self.player.stop();self.video.hide();self.image.hide();self.audio.setVolume(0);self.ready=False;self.loaded=False
    def status(self,status):
        if status==QMediaPlayer.LoadedMedia and not self.loaded:
            self.loaded=True;QTimer.singleShot(0,lambda:self.player.setPosition(max(clip_bounds(self.config,self.player.duration())[0],min(self.config.pop('_resume_ms',0),max(0,clip_bounds(self.config,self.player.duration())[1]-1)))))
        if status==QMediaPlayer.InvalidMedia:self.layer.error('無法解碼此媒體')
    def frame(self,f):
        if f.isValid():self.ready=True;self.last_frame=f
    def load(self,c):
        self.clear();self.config=deepcopy(c);p=c['path']
        if c.get('kind')!='black' and not Path(p).is_file():raise ValueError('媒體遺失：'+Path(p).name)
        if is_pdf(c):
            self.kind='pdf';self.item=self.image;self.pdf_source.load(p,c.get('pdf_page',0),QSizeF(self.layer.c['w'],self.layer.c['h']).toSize())
        elif c.get('kind')=='black':
            self.kind='image';self.item=self.image;pix=QPixmap(2,2);pix.fill(Qt.black);self.image.setPixmap(pix);self.ready=True
        elif Path(p).suffix.lower() in IMAGE_EXT:
            reader=QImageReader(p);reader.setAutoTransform(True);image=reader.read()
            if image.isNull():raise ValueError('圖片讀取失敗')
            self.kind='image';self.item=self.image;self.image.setPixmap(QPixmap.fromImage(image));self.ready=True
        else:
            self.kind='video';self.item=self.video;self.player.setSource(QUrl.fromLocalFile(p));self.player.play()
        self.layout();self.item.setOpacity(0);self.item.show()
    def layout(self):
        w,h=self.layer.c['w'],self.layer.c['h']
        # Tile geometry owns both axes. Keep the complete source mapped to its rectangle.
        self.image.setScale(1);self.image.setTransform(QTransform())
        if self.kind in ('image','pdf') and not self.image.pixmap().isNull():
            iw,ih=self.image.boundingRect().width(),self.image.boundingRect().height()
            self.image.setTransform(QTransform.fromScale(w/iw,h/ih));self.image.setPos(0,0)
        else:
            self.video.setAspectRatioMode(Qt.IgnoreAspectRatio);self.video.setSize(QSizeF(w,h));self.video.setPos(0,0);self.video.setScale(1)
        self.base=self.item.pos();self.scale=self.item.scale();self.item.setTransformOriginPoint(0,0)
    def freeze(self):
        self.player.pause()
        if self.kind=='video' and self.last_frame is not None:
            self.image.setPixmap(QPixmap.fromImage(self.last_frame.toImage()));self.image.setZValue(self.video.zValue())
            self.video.hide();self.kind='image';self.item=self.image;self.layout();self.image.setOpacity(1);self.image.show()
    def gain(self):
        return 0 if self.config.get('mute') else self.config.get('gain',100)/100

class Layer(QGraphicsRectItem):
    def __init__(self,panel,c):
        super().__init__(panel.host.screen.canvas_root);self.panel=panel;self.c=normalize_layer(c,len(panel.host.lists),panel.width_px,panel.height_px);self.capture=None;self.session=None
        self.setBrush(QBrush(Qt.black));self.setFlag(QGraphicsItem.ItemClipsChildrenToShape)
        self.setFlags(self.flags()|QGraphicsItem.ItemIsMovable|QGraphicsItem.ItemIsSelectable|QGraphicsItem.ItemSendsGeometryChanges)
        self.setCursor(Qt.OpenHandCursor);self.setZValue(10+len(panel.layers))
        self.label=EditorLabel(self.c['name'],self);self.label.setBrush(QColor('#6ee7d4'));self.label.setZValue(9999);self.label.setPos(8,8)
        self.handle=Handle(self);self.decks=[MediaDeck(self),MediaDeck(self)];self.active=0;self.current=None;self.pending=None;self.transition=None;self.elapsed=0;self.held=False;self.running=False
        self.resize_to(self.c['w'],self.c['h']);self.setPos(self.c['x'],self.c['y'])
        self.capture_video=QGraphicsVideoItem(self);self.capture_video.setZValue(3);self.capture_video.setSize(QSizeF(self.c['w'],self.c['h']));self.capture_video.setAspectRatioMode(Qt.IgnoreAspectRatio);self.capture_video.hide()
        self.editable(True)
    def paint(self,painter,option,widget=None):
        if clean_view(widget):
            painter.save();painter.setPen(Qt.NoPen);painter.setBrush(self.brush());painter.drawRect(self.rect());painter.restore()
        else:super().paint(painter,option,widget)
    def mouseDoubleClickEvent(self,event):
        self.panel.list.setCurrentRow(self.panel.layers.index(self))
        self.panel.replace_media();event.accept()
    def itemChange(self,change,value):
        if change==QGraphicsItem.ItemPositionChange and hasattr(self,'c'):
            from PySide6.QtCore import QPointF
            return QPointF(max(0,min(self.panel.width_px-self.c['w'],value.x())),max(0,min(self.panel.height_px-self.c['h'],value.y())))
        if change==QGraphicsItem.ItemPositionHasChanged and hasattr(self,'c'):
            self.c['x']=value.x();self.c['y']=value.y()
            if self.isSelected():self.panel.sync_controls()
        return super().itemChange(change,value)
    def resize_to(self,w,h):
        self.c['fit']=True;self.c['w'],self.c['h']=w,h;self.setRect(0,0,w,h);self.handle.setPos(w-22,h-22)
        for d in self.decks:d.layout()
        if hasattr(self,'capture_video'):self.capture_video.setSize(QSizeF(w,h));self.capture_video.setAspectRatioMode(Qt.IgnoreAspectRatio)
    def editable(self,enabled):
        self.setFlag(QGraphicsItem.ItemIsMovable,enabled);self.setFlag(QGraphicsItem.ItemIsSelectable,enabled)
        self.label.setVisible(enabled);self.handle.setVisible(enabled);self.setPen(QPen(QColor('#6ee7d4'),2) if enabled else QPen(Qt.NoPen))
    def error(self,message):
        self.stop();self.panel.host.status.setText(self.c['name']+'：'+message)
    def gain(self):
        return 0 if self.c.get('mute') else self.c.get('gain',100)/100*self.panel.host.volume.value()/100
    def start(self):
        if self.c['kind']!='playlist':self.start_capture();return
        self.running=True
        if self.held:self.request(self.current);return
        if self.current is None:self.request((self.c['group'],-1),initial=True)
        else:
            for d in self.decks:
                if d.kind=='video' and d.item.isVisible():d.player.play()
    def pause(self):
        self.running=False
        if self.capture:self.capture.stop()
        for d in self.decks:d.player.pause()
    def stop(self):
        self.held=False;self.running=False;self.pending=None;self.transition=None;self.current=None
        for d in self.decks:d.clear()
        if self.capture:self.capture.stop()
        if hasattr(self,'capture_video'):self.capture_video.hide()
    def dispose(self):
        self.stop()
        if self.session:self.session.setVideoOutput(None);self.session.deleteLater()
        if self.capture:self.capture.deleteLater()
        for d in self.decks:d.pdf_source.close();d.pdf_source.deleteLater();d.player.setVideoOutput(None);d.player.deleteLater();d.audio.deleteLater()
    def request(self,target,initial=False):
        host=self.panel.host
        if initial:target=self.next_target(target)
        if target is None:
            if self.panel.host.hold_last.isChecked() and self.current is not None:
                self.held=True;self.running=False;self.decks[self.active].freeze()
            else:self.stop()
            return
        if self.pending or self.transition:return
        self.held=False
        p,i=target
        items=self.source_items()
        if not 0<=i<len(items):self.stop();return
        if is_powerpoint(items[i]):
            host.status.setText('PowerPoint 動畫簡報使用獨立原生輸出，請切回單畫面播放。');self.stop();return
        initial_load=self.current is None
        self.current=target;self.running=True;idx=1-self.active;self.pending=(idx,time.monotonic());self.elapsed=0
        try:
            item=deepcopy(items[i])
            if initial_load and 'cue_position' in self.c:item['_resume_ms']=self.c['cue_position']
            self.decks[idx].load(item)
        except Exception as e:self.error(str(e))
    def source_items(self):
        if 'items' in self.c:return self.c['items']
        group=self.c['group'];return self.panel.host.lists[group]['items'] if 0<=group<len(self.panel.host.lists) else []
    def next_target(self,current=None,reverse=False):
        # Each tile stays bound to its own source list, including single-file mode.
        group=self.c['group'];lists=self.panel.host.lists
        items=self.source_items()
        if not items:return None
        if self.current is None and 'cue_index' in self.c:return (group,min(len(items)-1,int(self.c['cue_index'])))
        current=current or self.current or (group,-1)
        mode=self.panel.host.mode.currentText()
        if mode=='所有清單輪播':mode='清單循環'
        result=following([{'items':items}],(0,current[1]),mode,reverse)
        return (group,result[1]) if result is not None else None
    def advance(self,reverse=False):
        if self.c['kind']=='playlist':
            d=self.decks[self.active]
            if d.kind=='pdf' and not self.pending and not self.transition and d.pdf_source.step(reverse):self.elapsed=0;return
            target=self.next_target(reverse=reverse)
            if target==self.current and not self.pending and not self.transition:
                self.elapsed=0
                if d.kind=='pdf':d.pdf_source.set_page(d.pdf_source.count-1 if reverse else 0)
                if d.kind=='video':d.player.setPosition(clip_bounds(d.config,d.player.duration())[0]);d.player.play()
                return
            self.request(target)
    def tick(self,dt):
        if not self.running or self.c['kind']!='playlist':return
        host=self.panel.host
        if self.pending:
            idx,started=self.pending
            if not self.decks[idx].ready:
                if time.monotonic()-started>20:self.error('解碼逾時')
                return
            effect='直接切換' if self.panel.performance.isChecked() else host.effect.currentText()
            if effect=='隨機效果':effect=random.choice(EFFECTS[:-1])
            self.pending=None;self.transition=[idx,self.active,0,effect]
            self.decks[idx].item.setZValue(2);self.decks[self.active].item.setZValue(1)
        if self.transition:
            new,old,t,effect=self.transition;t+=dt;self.transition[2]=t
            f=1 if effect=='直接切換' else min(1,t/host.duration.value());a,b=self.decks[old],self.decks[new]
            ag,bg=1-f,f
            if effect=='淡出至黑再淡入':ag=max(0,1-2*f);bg=max(0,2*f-1)
            a.item.setOpacity(ag if effect=='淡出至黑再淡入' else 1);b.item.setOpacity(bg)
            if effect in ('向左滑動','向右滑動'):b.item.setPos(b.base.x()+(1-f)*self.c['w']*(1 if effect=='向左滑動' else -1),b.base.y())
            if effect=='縮放淡入':b.item.setScale(b.scale*(.85+.15*f))
            a.audio.setVolume(ag*self.gain()*a.gain());b.audio.setVolume(bg*self.gain()*b.gain())
            if f>=1:a.clear();b.layout();b.item.setOpacity(1);self.active=new;self.transition=None;self.elapsed=0
            return
        d=self.decks[self.active];d.audio.setVolume(self.gain()*d.gain())
        if d.kind=='pdf':
            if host.pdf_auto.isChecked() and not d.pdf_source.loading:
                self.elapsed+=dt
                if self.elapsed>=d.config.get('seconds',5):self.elapsed=0;self.advance()
            return
        if d.kind=='image':
            self.elapsed+=dt
            if self.elapsed>=d.config.get('seconds',5):self.advance()
        else:
            start,end=clip_bounds(d.config,d.player.duration())
            if d.player.mediaStatus()==QMediaPlayer.EndOfMedia or (end and d.player.position()>=end):self.advance()
            elif not self.panel.performance.isChecked() and end and end-start>host.duration.value()*2000 and 0<end-d.player.position()<=host.duration.value()*1000 and host.effect.currentText()!='直接切換':
                if self.next_target() not in (None,self.current):self.advance()
    def start_capture(self):
        self.stop();kind=self.c['kind'];host=self.panel.host
        if self.session:self.session.setVideoOutput(None);self.session.deleteLater()
        if self.capture:self.capture.deleteLater()
        self.session=QMediaCaptureSession();self.session.setVideoOutput(self.capture_video)
        key=self.c.get('source','')
        try:
            if kind=='camera':
                sources=QMediaDevices.videoInputs();device=next((d for d in sources if bytes(d.id()).hex()==key),None)
                if device is None:raise ValueError('攝影機／擷取卡已離線，請重新選擇來源')
                self.capture=QCamera(device);self.session.setCamera(self.capture)
            elif kind=='screen':
                sources=host.screen.screen().virtualSiblings();device=next((s for s in sources if s.name()==key),None)
                if device is None:raise ValueError('螢幕已離線，請重新選擇來源')
                self.capture=QScreenCapture();self.capture.setScreen(device);self.session.setScreenCapture(self.capture)
            else:
                sources=QWindowCapture.capturableWindows();device=next((w for w in sources if str(w.id())==key and w.description()==self.c.get('source_title')),None)
                if device is None:raise ValueError('視窗已關閉或重新開啟，請重新選擇來源')
                self.capture=QWindowCapture();self.capture.setWindow(device);self.session.setWindowCapture(self.capture)
            self.capture.errorOccurred.connect(lambda e,m:self.error('擷取失敗：'+m));self.capture_video.show();self.capture.start();self.running=True
        except Exception as e:self.error(str(e))

class Compositor(QDockWidget):
    def __init__(self,host):
        super().__init__('多畫面／場景',host);self.host=host;self.layers=[];self.scenes=[];self.enabled=False;self.updating=False
        self.setObjectName('InspectorDock');host.addDockWidget(Qt.RightDockWidgetArea,self)
        self.tabs=QTabWidget();self.setWidget(self.tabs)
        def page(title):
            scroll=QScrollArea();scroll.setWidgetResizable(True);body=QWidget();body.setProperty('panel',True);scroll.setWidget(body);layout=QVBoxLayout(body);layout.setContentsMargins(12,12,12,12);layout.setSpacing(9);self.tabs.addTab(scroll,title);return layout
        v=page('多畫面')
        self.enable=QCheckBox('啟用多畫面（最多 12 個）');v.addWidget(self.enable);self.enable.toggled.connect(self.set_enabled)
        self.edit=QCheckBox('顯示格子拖曳框與尺寸控制');self.edit.setChecked(True);v.addWidget(self.edit);self.edit.toggled.connect(self.editable)
        self.performance=QCheckBox('效能模式（直接切換）');self.performance.setChecked(True);v.addWidget(self.performance)
        self.list=QListWidget();self.list.setMaximumHeight(160);self.list.setMinimumHeight(80);v.addWidget(self.list);self.list.currentRowChanged.connect(self.select_layer)
        r=QHBoxLayout();v.addLayout(r);self.button(r,'＋ 畫面',self.add_playlist);self.button(r,'外部擷取',self.add_capture);self.button(r,'移除',self.remove)
        self.button(v,'從播放列表選檔',self.replace_media)
        self.group=QComboBox();v.addWidget(self.group);self.group.currentIndexChanged.connect(self.change_group)
        r=QHBoxLayout();v.addLayout(r);self.button(r,'2×2',lambda:self.grid(2,2));self.button(r,'3×2',lambda:self.grid(3,2));self.button(r,'4×3',lambda:self.grid(4,3))
        self.templates=QComboBox();self.templates.addItems(['左右雙畫面','上下雙畫面','三欄','三列','主畫面＋右側兩格','左上子畫面','右下子畫面','自訂欄列']);v.addWidget(self.templates);self.button(v,'套用版型',self.apply_template);v.addStretch()
        v=page('尺寸／聲音');self.controls={}
        for key,label,low,high in [('x','左',0,1920),('y','上',0,1080),('w','寬',80,1920),('h','高',45,1080),('gain','畫面音量 %',0,100)]:
            r=QHBoxLayout();v.addLayout(r);r.addWidget(QLabel(label));spin=QDoubleSpinBox();spin.setRange(low,high);spin.setDecimals(0);r.addWidget(spin);self.controls[key]=spin;spin.valueChanged.connect(self.update_layer)
        r=QHBoxLayout();v.addLayout(r);self.button(r,'縮小 −10%',lambda:self.scale_selected(.9));self.button(r,'放大 ＋10%',lambda:self.scale_selected(1.1));self.button(r,'填滿此格',self.full_bleed)
        self.mute=QCheckBox('此畫面靜音');v.addWidget(self.mute);self.mute.toggled.connect(self.update_layer)
        self.fit=QCheckBox('影像強制鋪滿格子（拉伸）');self.fit.setChecked(True);self.fit.setEnabled(False);v.addWidget(self.fit);self.fit.toggled.connect(self.update_layer)
        r=QHBoxLayout();v.addLayout(r);self.button(r,'移到上層',lambda:self.reorder(1));self.button(r,'移到下層',lambda:self.reorder(-1));v.addStretch()
        playback=QScrollArea();playback.setWidgetResizable(True);playback.setWidget(host.interface.playback_widget);self.tabs.addTab(playback,'播放／輸出')
        self.scene_list=QComboBox(self);self.scene_list.hide()
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(16);self.last=time.monotonic()
        self.refresh_groups();host.screen.scene().selectionChanged.connect(self.scene_selection)
    @property
    def width_px(self):return self.host.screen.sceneRect().width()
    @property
    def height_px(self):return self.host.screen.sceneRect().height()
    def button(self,row,name,fn):
        b=QPushButton(name);row.addWidget(b);b.clicked.connect(lambda _=False:fn());return b
    def refresh_groups(self):
        self.group.blockSignals(True);self.group.clear();self.group.addItems([g['name'] for g in self.host.lists]);self.group.blockSignals(False)
    def set_enabled(self,value):
        self.host.stop_single();self.enabled=value;self.host.seek.setEnabled(not value)
        for l in self.layers:l.setVisible(value);l.stop()
        self.host.status.setText('多畫面模式：按播放啟動所有來源' if value else '單畫面模式')
    def editable(self,value):
        for l in self.layers:l.editable(value)
    def scene_selection(self):
        selected=self.host.screen.scene().selectedItems()
        if selected and selected[0] in self.layers:self.list.setCurrentRow(self.layers.index(selected[0]))
    def selected(self):
        row=self.list.currentRow();return self.layers[row] if 0<=row<len(self.layers) else None
    def select_layer(self,row):
        for i,l in enumerate(self.layers):l.setSelected(i==row and self.edit.isChecked())
        self.sync_controls()
    def sync_controls(self):
        l=self.selected()
        if not l:return
        self.updating=True
        for key,spin in self.controls.items():spin.setValue(l.c[key])
        self.group.setCurrentIndex(l.c['group']);self.mute.setChecked(l.c['mute']);self.fit.setChecked(l.c['fit']);self.updating=False
    def update_layer(self,*_):
        if self.updating:return
        l=self.selected()
        if not l:return
        c=dict(l.c)
        for key,spin in self.controls.items():c[key]=spin.value()
        c['mute']=self.mute.isChecked();c['fit']=self.fit.isChecked();l.c=normalize_layer(c,len(self.host.lists),self.width_px,self.height_px);l.resize_to(l.c['w'],l.c['h']);l.setPos(l.c['x'],l.c['y']);self.sync_controls()
    def change_group(self,index):
        if self.updating:return
        l=self.selected()
        if l:
            l.stop();l.c['group']=max(0,index);l.c.pop('items',None);l.c.pop('cue_index',None);l.c.pop('cue_position',None)
    def add(self,c):
        if len(self.layers)>=MAX_LAYERS:QMessageBox.information(self.host,'畫面上限','最多可添加 12 個畫面。');return
        l=Layer(self,c);self.layers.append(l);l.setVisible(self.enabled);l.editable(self.edit.isChecked());self.refresh();self.list.setCurrentRow(len(self.layers)-1)
    def add_playlist(self):
        self.enable.setChecked(True);self.add({'kind':'playlist','group':self.host.group_index(),'name':f'畫面 {len(self.layers)+1}','x':40*len(self.layers),'y':30*len(self.layers),'w':640,'h':360})
    def replace_media(self):
        l=self.selected()
        if l is None:
            self.host.status.setText('請先選擇格子，或按 2×2 建立格子');return
        choices=[(g,i,f"{g+1}-{i+1}｜{group['name']} / {media_name(item)}") for g,group in enumerate(self.host.lists) for i,item in enumerate(group['items'])]
        if not choices:self.host.status.setText('請先將檔案加入左側播放列表');return
        labels=[x[2] for x in choices]
        choice,ok=QInputDialog.getItem(self.host,'從播放列表選擇','此格要播放的檔案',labels,0,False)
        if ok:
            g,i,_=choices[labels.index(choice)];self.assign_items(l,[self.host.lists[g]['items'][i]])
    def use_selected_file(self):
        l=self.selected();g=self.host.group_index();i=self.host.files.currentRow()
        if l is None:self.host.status.setText('請先點選畫布上的格子');return
        if not 0<=i<len(self.host.lists[g]['items']):self.host.status.setText('請先在左側選取檔案');return
        self.assign_items(l,[self.host.lists[g]['items'][i]])
    def assign_items(self,l,items):
        if not items:return
        if any(is_powerpoint(item) for item in items):
            self.host.status.setText('PPT 動畫與音效使用 PowerPoint 獨立輸出，請切回單畫面後播放。');return
        l.stop();name=media_name(items[0])
        l.c.update(kind='playlist',name=name,fit=True,items=deepcopy(items));l.c.pop('cue_index',None);l.c.pop('cue_position',None)
        l.label.setText(name);l.resize_to(l.c['w'],l.c['h'])
        self.refresh();self.list.setCurrentRow(self.layers.index(l));self.sync_controls()
        self.enable.setChecked(True);l.start();self.host.persist_session()
    def assign_media(self,l,paths):
        self.assign_items(l,[{'path':p,'seconds':5,'start':0,'end':0,'gain':100,'mute':False} for p in paths])
    def scale_selected(self,factor):
        l=self.selected()
        if not l:return
        scale=max(80/l.c['w'],45/l.c['h'],min(factor,self.width_px/l.c['w'],self.height_px/l.c['h']))
        w,h=l.c['w']*scale,l.c['h']*scale
        cx,cy=l.pos().x()+l.c['w']/2,l.pos().y()+l.c['h']/2
        l.resize_to(w,h);l.setPos(max(0,min(self.width_px-w,cx-w/2)),max(0,min(self.height_px-h,cy-h/2)))
        self.sync_controls();self.host.persist_session()
    def full_bleed(self):
        l=self.selected()
        if not l:return
        l.c['fit']=True;l.resize_to(l.c['w'],l.c['h'])
        self.sync_controls();self.host.persist_session()
        self.host.status.setText('已強制拉伸鋪滿此格；格子位置與尺寸不變。')
    def add_capture(self):
        kind,ok=QInputDialog.getItem(self.host,'外部擷取','來源種類',['攝影機／USB HDMI 擷取卡','螢幕','應用程式視窗'],0,False)
        if not ok:return
        if kind.startswith('攝影機'):k='camera';sources=[(d.description(),bytes(d.id()).hex()) for d in QMediaDevices.videoInputs()]
        elif kind=='螢幕':k='screen';sources=[(s.name(),s.name()) for s in self.host.screen.screen().virtualSiblings()]
        else:k='window';sources=[(w.description(),str(w.id())) for w in QWindowCapture.capturableWindows()]
        if not sources:QMessageBox.information(self.host,'沒有可用來源','請確認裝置連接及系統擷取權限。');return
        labels=[f'{i+1}. {s[0]}' for i,s in enumerate(sources)]
        name,ok=QInputDialog.getItem(self.host,'選擇來源','來源（擷取不含系統聲音）',labels,0,False)
        if ok:
            title,key=sources[labels.index(name)];self.enable.setChecked(True);self.add({'kind':k,'name':title,'source':key,'source_title':title,'w':640,'h':360})
    def refresh(self):
        row=self.list.currentRow();self.list.blockSignals(True);self.list.clear();self.list.addItems([l.c['name'] for l in self.layers]);self.list.setCurrentRow(min(row,len(self.layers)-1));self.list.blockSignals(False)
        for i,l in enumerate(self.layers):l.setZValue(10+i)
    def remove(self):
        l=self.selected()
        if l:l.dispose();self.host.screen.scene().removeItem(l);self.layers.remove(l);self.refresh();self.sync_controls()
    def reorder(self,delta):
        i=self.list.currentRow();j=i+delta
        if 0<=i<len(self.layers) and 0<=j<len(self.layers):self.layers[i],self.layers[j]=self.layers[j],self.layers[i];self.refresh();self.list.setCurrentRow(j)
    def grid(self,cols,rows):
        if self.width_px/cols<80 or self.height_px/rows<45:
            QMessageBox.information(self.host,'畫布太小','請增加畫布像素，讓每格至少 80×45。');return
        if len(self.layers)>cols*rows:
            QMessageBox.information(self.host,'格子數不足','請先移除多餘畫面，再選擇此排列。');return
        self.enable.setChecked(True)
        while len(self.layers)<cols*rows:
            name=f'畫面 {len(self.layers)+1}（雙擊選檔）'
            self.add({'kind':'playlist','group':0,'items':[],'name':name,'fit':True})
        for i,l in enumerate(self.layers):
            l.c['fit']=True
            l.resize_to(self.width_px/cols,self.height_px/rows);l.setPos((i%cols)*self.width_px/cols,(i//cols)*self.height_px/rows)
        self.list.setCurrentRow(0);self.sync_controls();self.host.persist_session()
        self.host.status.setText('選取格子後，選左側檔案並按「套用到選取格子」；每格強制拉伸滿版。')
    def apply_template(self):
        name=self.templates.currentText()
        grids={'左右雙畫面':(2,1),'上下雙畫面':(1,2),'三欄':(3,1),'三列':(1,3)}
        if name in grids:self.grid(*grids[name]);return
        if name=='自訂欄列':
            cols,ok=QInputDialog.getInt(self.host,'自訂面板','欄數',2,1,12)
            if not ok:return
            rows,ok=QInputDialog.getInt(self.host,'自訂面板','列數（總格數最多 12）',1,1,12//cols)
            if ok:self.grid(cols,rows)
            return
        rects=[(0,0,.7,1),(.7,0,.3,.5),(.7,.5,.3,.5)] if name=='主畫面＋右側兩格' else [(0,0,1,1),(.03,.03,.3,.3) if name=='左上子畫面' else (.67,.67,.3,.3)]
        if len(self.layers)>len(rects):
            QMessageBox.information(self.host,'畫面數過多','請先移除多餘畫面再套用此版型。');return
        self.grid(len(rects),1)
        for l,(x,y,w,h) in zip(self.layers,rects):
            l.resize_to(w*self.width_px,h*self.height_px);l.setPos(x*self.width_px,y*self.height_px)
        self.sync_controls();self.host.persist_session()
    def snapshot(self):return [deepcopy(l.c) for l in self.layers]
    def restore(self,layout):
        for l in self.layers:l.dispose();self.host.screen.scene().removeItem(l)
        self.layers=[];self.refresh()
        for c in layout:self.add(c)
    def capture_cue(self,name):
        if self.host.pending or self.host.transition or any(l.pending or l.transition for l in self.layers):
            raise ValueError('請等待媒體載入或轉場完成後再記錄 CUE。')
        if not self.enabled and self.host.current is None:raise ValueError('請先播放要記憶的影像再記錄 CUE。')
        layout=self.snapshot()
        for c,l in zip(layout,self.layers):
            if c['kind']=='playlist':
                c['items']=deepcopy(l.source_items());c['cue_index']=l.current[1] if l.current else 0
                c['cue_position']=l.decks[l.active].player.position() if l.current and l.decks[l.active].kind=='video' else 0
        single=None
        if not self.enabled and self.host.current is not None:
            d=self.host.decks[self.host.active]
            single={'media':deepcopy(self.host.current_item()),'position':d.player.position() if d.kind=='video' and not self.host.presentations.active else 0}
        return {'name':name,'cue_version':1,'layout':layout,'settings':self.host.settings(),'single':single}
    def remember(self):
        name,ok=QInputDialog.getText(self.host,'記錄 CUE','段落／場景名稱')
        if ok and name.strip():
            try:cue=self.capture_cue(name.strip())
            except ValueError as e:self.host.status.setText(str(e));return
            self.scenes.append(cue);self.refresh_scenes();self.scene_list.setCurrentIndex(len(self.scenes)-1);self.host.persist_session()
    def refresh_scenes(self):self.scene_list.clear();self.scene_list.addItems([f"CUE {i+1:02d} · {s['name']}" for i,s in enumerate(self.scenes)])
    def recall(self):
        i=self.scene_list.currentIndex()
        if i<0:return
        s=deepcopy(self.scenes[i]);settings=s.get('settings',{});multi=bool(settings.get('multi',True))
        # Check every stored source before interrupting the current show.
        from model import media_walk
        missing=[]
        media_walk(s['layout'] if multi else s.get('single'),lambda item:missing.append(media_name(item)) if item.get('kind')!='black' and not Path(item['path']).is_file() else None)
        if missing:self.host.status.setText('CUE 媒體遺失，保留目前畫面：'+', '.join(missing));return
        self.host.stop();self.host.apply_settings(settings);self.enable.setChecked(multi);self.restore(s['layout'])
        if multi:
            for l in self.layers:l.start()
        elif s.get('single'):
            item=deepcopy(s['single']['media']);item['_resume_ms']=s['single'].get('position',0);self.host.request((0,0),item_override=item)
        else:
            self.host.status.setText('舊場景沒有保存單畫面來源，請重新記錄 CUE。');return
        self.host.status.setText(f"CUE {i+1:02d} GO · {s['name']}")
    def next_cue(self):
        i=self.scene_list.currentIndex()+1
        if i>=len(self.scenes):self.host.status.setText('已到最後一個 CUE');return
        self.scene_list.setCurrentIndex(i);self.recall()
    def overwrite(self):
        i=self.scene_list.currentIndex()
        if i>=0:
            try:self.scenes[i]=self.capture_cue(self.scenes[i]['name'])
            except ValueError as e:self.host.status.setText(str(e));return
            self.host.persist_session()
    def rename_scene(self):
        i=self.scene_list.currentIndex()
        if i<0:return
        name,ok=QInputDialog.getText(self.host,'場景改名','場景名稱',text=self.scenes[i]['name'])
        if ok and name.strip():
            self.scenes[i]['name']=name.strip()[:120];self.refresh_scenes();self.scene_list.setCurrentIndex(i);self.host.persist_session()
    def delete_scene(self):
        i=self.scene_list.currentIndex()
        if i>=0:self.scenes.pop(i);self.refresh_scenes();self.host.persist_session()
    def toggle(self):
        if any(l.running for l in self.layers):
            for l in self.layers:l.pause()
            self.host.status.setText('多畫面已暫停')
        else:
            for l in self.layers:l.start()
            self.host.status.setText('多畫面播放中；解碼錯誤會停止該來源')
    def stop(self):
        for l in self.layers:l.stop()
    def advance(self,reverse=False):
        for l in self.layers:l.advance(reverse)
    def tick(self):
        now=time.monotonic();dt=min(.25,now-self.last);self.last=now
        if self.enabled:
            for l in self.layers:l.tick(dt)


