"""Native Qt compositor: independent dual media decks and explicitly enabled capture."""
import time, random
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QSizeF, QUrl, QRectF
from PySide6.QtGui import QPen, QColor, QBrush, QPixmap, QImageReader
from PySide6.QtWidgets import (QGraphicsRectItem,QGraphicsItem,QGraphicsSimpleTextItem,
    QDockWidget,QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QListWidget,QComboBox,
    QLabel,QDoubleSpinBox,QCheckBox,QInputDialog,QMessageBox,QFileDialog)
from PySide6.QtMultimedia import (QMediaPlayer,QAudioOutput,QMediaCaptureSession,
    QCamera,QMediaDevices,QScreenCapture,QWindowCapture)
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from model import IMAGE_EXT,EFFECTS,following,clip_bounds,normalize_layer,MAX_LAYERS

class Handle(QGraphicsRectItem):
    def __init__(self,parent):
        super().__init__(0,0,22,22,parent);self.setBrush(QColor('#6ee7d4'));self.setPen(QPen(Qt.NoPen));self.setZValue(10000)
        self.setCursor(Qt.SizeFDiagCursor)
    def mousePressEvent(self,e):
        self.origin=e.scenePos();p=self.parentItem();self.size=(p.c['w'],p.c['h']);e.accept()
    def mouseMoveEvent(self,e):
        p=self.parentItem();delta=e.scenePos()-self.origin
        p.resize_to(min(1920-p.pos().x(),max(80,self.size[0]+delta.x())),min(1080-p.pos().y(),max(45,self.size[1]+delta.y())))
        p.panel.sync_controls();e.accept()

class MediaDeck:
    def __init__(self,layer):
        self.layer=layer;self.video=QGraphicsVideoItem(layer);
        from PySide6.QtWidgets import QGraphicsPixmapItem
        self.image=QGraphicsPixmapItem(layer)
        self.player=QMediaPlayer();self.audio=QAudioOutput();self.player.setAudioOutput(self.audio);self.player.setVideoOutput(self.video)
        self.kind='image';self.item=self.image;self.config={};self.ready=False;self.loaded=False
        self.player.mediaStatusChanged.connect(self.status)
        self.player.errorOccurred.connect(lambda e,m:layer.error(m))
        self.video.videoSink().videoFrameChanged.connect(self.frame)
        self.clear()
    def clear(self):
        self.player.stop();self.video.hide();self.image.hide();self.audio.setVolume(0);self.ready=False;self.loaded=False
    def status(self,status):
        if status==QMediaPlayer.LoadedMedia and not self.loaded:
            self.loaded=True;QTimer.singleShot(0,lambda:self.player.setPosition(clip_bounds(self.config,self.player.duration())[0]))
        if status==QMediaPlayer.InvalidMedia:self.layer.error('無法解碼此媒體')
    def frame(self,f):
        if f.isValid():self.ready=True
    def load(self,c):
        self.clear();self.config=deepcopy(c);p=c['path']
        if not Path(p).is_file():raise ValueError('媒體遺失：'+Path(p).name)
        if Path(p).suffix.lower() in IMAGE_EXT:
            reader=QImageReader(p);reader.setAutoTransform(True);image=reader.read()
            if image.isNull():raise ValueError('圖片讀取失敗')
            self.kind='image';self.item=self.image;self.image.setPixmap(QPixmap.fromImage(image));self.ready=True
        else:
            self.kind='video';self.item=self.video;self.player.setSource(QUrl.fromLocalFile(p));self.player.play()
        self.layout();self.item.setOpacity(0);self.item.show()
    def layout(self):
        w,h=self.layer.c['w'],self.layer.c['h']
        if self.kind=='image' and not self.image.pixmap().isNull():
            iw,ih=self.image.pixmap().width(),self.image.pixmap().height()
            s=(max if self.layer.c.get('fit') else min)(w/iw,h/ih)
            self.image.setScale(s);self.image.setPos((w-iw*s)/2,(h-ih*s)/2)
        else:
            self.video.setSize(QSizeF(w,h));self.video.setAspectRatioMode(Qt.KeepAspectRatioByExpanding if self.layer.c.get('fit') else Qt.KeepAspectRatio);self.video.setPos(0,0);self.video.setScale(1)
        self.base=self.item.pos();self.scale=self.item.scale();self.item.setTransformOriginPoint(self.item.boundingRect().center())
    def gain(self):
        return 0 if self.config.get('mute') else self.config.get('gain',100)/100

class Layer(QGraphicsRectItem):
    def __init__(self,panel,c):
        super().__init__();self.panel=panel;self.c=normalize_layer(c,len(panel.host.lists));self.capture=None;self.session=None
        self.setBrush(QBrush(Qt.black));self.setFlag(QGraphicsItem.ItemClipsChildrenToShape)
        self.setFlags(self.flags()|QGraphicsItem.ItemIsMovable|QGraphicsItem.ItemIsSelectable|QGraphicsItem.ItemSendsGeometryChanges)
        self.setCursor(Qt.OpenHandCursor);self.setZValue(10+len(panel.layers))
        self.label=QGraphicsSimpleTextItem(self.c['name'],self);self.label.setBrush(QColor('#6ee7d4'));self.label.setZValue(9999);self.label.setPos(8,8)
        self.handle=Handle(self);self.decks=[MediaDeck(self),MediaDeck(self)];self.active=0;self.current=None;self.pending=None;self.transition=None;self.elapsed=0;self.running=False
        self.resize_to(self.c['w'],self.c['h']);self.setPos(self.c['x'],self.c['y'])
        self.capture_video=QGraphicsVideoItem(self);self.capture_video.setZValue(3);self.capture_video.setSize(QSizeF(self.c['w'],self.c['h']));self.capture_video.hide()
        self.editable(True)
    def itemChange(self,change,value):
        if change==QGraphicsItem.ItemPositionChange and hasattr(self,'c'):
            from PySide6.QtCore import QPointF
            return QPointF(max(0,min(1920-self.c['w'],value.x())),max(0,min(1080-self.c['h'],value.y())))
        if change==QGraphicsItem.ItemPositionHasChanged and hasattr(self,'c'):
            self.c['x']=value.x();self.c['y']=value.y()
            if self.isSelected():self.panel.sync_controls()
        return super().itemChange(change,value)
    def resize_to(self,w,h):
        self.c['w'],self.c['h']=w,h;self.setRect(0,0,w,h);self.handle.setPos(w-22,h-22)
        for d in self.decks:d.layout()
        if hasattr(self,'capture_video'):self.capture_video.setSize(QSizeF(w,h))
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
        if self.current is None:self.request((self.c['group'],-1),initial=True)
        else:
            for d in self.decks:
                if d.kind=='video' and d.item.isVisible():d.player.play()
    def pause(self):
        self.running=False
        if self.capture:self.capture.stop()
        for d in self.decks:d.player.pause()
    def stop(self):
        self.running=False;self.pending=None;self.transition=None;self.current=None
        for d in self.decks:d.clear()
        if self.capture:self.capture.stop()
        if hasattr(self,'capture_video'):self.capture_video.hide()
    def dispose(self):
        self.stop()
        if self.session:self.session.setVideoOutput(None);self.session.deleteLater()
        if self.capture:self.capture.deleteLater()
        for d in self.decks:d.player.setVideoOutput(None);d.player.deleteLater();d.audio.deleteLater()
    def request(self,target,initial=False):
        host=self.panel.host
        if initial:target=following(host.lists,target,host.mode.currentText())
        if target is None:self.stop();return
        if self.pending or self.transition:return
        p,i=target
        if not (0<=p<len(host.lists) and 0<=i<len(host.lists[p]['items'])):self.stop();return
        self.current=target;self.running=True;idx=1-self.active;self.pending=(idx,time.monotonic());self.elapsed=0
        try:self.decks[idx].load(host.lists[p]['items'][i])
        except Exception as e:self.error(str(e))
    def advance(self,reverse=False):
        if self.c['kind']=='playlist':self.request(following(self.panel.host.lists,self.current or (self.c['group'],-1),self.panel.host.mode.currentText(),reverse))
    def tick(self,dt):
        if not self.running or self.c['kind']!='playlist':return
        host=self.panel.host
        if self.pending:
            idx,started=self.pending
            if not self.decks[idx].ready:
                if time.monotonic()-started>20:self.error('解碼逾時')
                return
            effect=host.effect.currentText()
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
        if d.kind=='image':
            self.elapsed+=dt
            if self.elapsed>=d.config.get('seconds',5):self.advance()
        else:
            start,end=clip_bounds(d.config,d.player.duration())
            if d.player.mediaStatus()==QMediaPlayer.EndOfMedia or (end and d.player.position()>=end):self.advance()
            elif end and end-start>host.duration.value()*2000 and 0<end-d.player.position()<=host.duration.value()*1000 and host.effect.currentText()!='直接切換':
                if following(host.lists,self.current,host.mode.currentText()) is not None:self.advance()
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
        host.addDockWidget(Qt.RightDockWidgetArea,self);self.setMinimumWidth(310)
        body=QWidget();self.setWidget(body);v=QVBoxLayout(body)
        self.enable=QCheckBox('啟用多畫面（最多 12 個）');v.addWidget(self.enable);self.enable.toggled.connect(self.set_enabled)
        self.edit=QCheckBox('顯示拖曳框與尺寸控制');self.edit.setChecked(True);v.addWidget(self.edit);self.edit.toggled.connect(self.editable)
        self.list=QListWidget();v.addWidget(self.list);self.list.currentRowChanged.connect(self.select_layer)
        row=QHBoxLayout();v.addLayout(row)
        self.button(row,'＋清單畫面',self.add_playlist);self.button(row,'＋外部擷取',self.add_capture);self.button(row,'移除',self.remove)
        row=QHBoxLayout();v.addLayout(row);self.button(row,'＋照片／影片',self.add_media)
        self.group=QComboBox();v.addWidget(self.group);self.group.currentIndexChanged.connect(self.change_group)
        self.controls={}
        for key,label,low,high in [('x','左',0,1920),('y','上',0,1080),('w','寬',80,1920),('h','高',45,1080),('gain','畫面音量 %',0,100)]:
            row=QHBoxLayout();v.addLayout(row);row.addWidget(QLabel(label));spin=QDoubleSpinBox();spin.setRange(low,high);spin.setDecimals(0);row.addWidget(spin);self.controls[key]=spin;spin.valueChanged.connect(self.update_layer)
        row=QHBoxLayout();v.addLayout(row)
        self.button(row,'縮小 −10%',lambda:self.scale_selected(.9));self.button(row,'放大 ＋10%',lambda:self.scale_selected(1.1));self.button(row,'一鍵滿版',self.full_bleed)
        self.mute=QCheckBox('此畫面靜音');v.addWidget(self.mute);self.mute.toggled.connect(self.update_layer)
        self.fit=QCheckBox('填滿此畫面（裁切）');v.addWidget(self.fit);self.fit.toggled.connect(self.update_layer)
        row=QHBoxLayout();v.addLayout(row);self.button(row,'移到上層',lambda:self.reorder(1));self.button(row,'移到下層',lambda:self.reorder(-1))
        row=QHBoxLayout();v.addLayout(row);self.button(row,'2×2',lambda:self.grid(2,2));self.button(row,'3×2',lambda:self.grid(3,2));self.button(row,'4×3',lambda:self.grid(4,3))
        v.addWidget(QLabel('場景記憶（自動保存）'))
        self.scene_list=QComboBox();v.addWidget(self.scene_list)
        row=QHBoxLayout();v.addLayout(row);self.button(row,'記憶新場景',self.remember);self.button(row,'載入',self.recall);self.button(row,'覆寫',self.overwrite);self.button(row,'改名',self.rename_scene);self.button(row,'刪除',self.delete_scene)
        note=QLabel('輸出固定 1920×1080。外部擷取由「播放」啟動；場景載入後需重新播放。擷取卡須為系統可識別的攝影機裝置。');note.setWordWrap(True);v.addWidget(note)
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(16);self.last=time.monotonic()
        self.refresh_groups();host.screen.scene().selectionChanged.connect(self.scene_selection)
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
        c['mute']=self.mute.isChecked();c['fit']=self.fit.isChecked();l.c=normalize_layer(c,len(self.host.lists));l.resize_to(l.c['w'],l.c['h']);l.setPos(l.c['x'],l.c['y']);self.sync_controls()
    def change_group(self,index):
        if self.updating:return
        l=self.selected()
        if l:l.stop();l.c['group']=max(0,index)
    def add(self,c):
        if len(self.layers)>=MAX_LAYERS:QMessageBox.information(self.host,'畫面上限','最多可添加 12 個畫面。');return
        l=Layer(self,c);self.host.screen.scene().addItem(l);self.layers.append(l);l.setVisible(self.enabled);l.editable(self.edit.isChecked());self.refresh();self.list.setCurrentRow(len(self.layers)-1)
    def add_playlist(self):
        self.enable.setChecked(True);self.add({'kind':'playlist','group':self.host.group_index(),'name':f'畫面 {len(self.layers)+1}','x':40*len(self.layers),'y':30*len(self.layers),'w':640,'h':360})
    def add_media(self):
        if len(self.layers)>=MAX_LAYERS:
            QMessageBox.information(self.host,'畫面上限','最多可添加 12 個畫面。');return
        paths,_=QFileDialog.getOpenFileNames(self.host,'新增照片／影片畫面','','所有檔案 (*)')
        if not paths:return
        group=len(self.host.lists)
        self.host.lists.append({'name':Path(paths[0]).stem,'items':[{'path':p,'seconds':5,'start':0,'end':0,'gain':100,'mute':False} for p in paths]})
        self.host.refresh_groups(group);self.enable.setChecked(True)
        self.add({'kind':'playlist','group':group,'name':Path(paths[0]).stem,'w':640,'h':360})
        self.host.persist_session()
    def scale_selected(self,factor):
        l=self.selected()
        if not l:return
        scale=max(80/l.c['w'],45/l.c['h'],min(factor,1920/l.c['w'],1080/l.c['h']))
        w,h=l.c['w']*scale,l.c['h']*scale
        cx,cy=l.pos().x()+l.c['w']/2,l.pos().y()+l.c['h']/2
        l.resize_to(w,h);l.setPos(max(0,min(1920-w,cx-w/2)),max(0,min(1080-h,cy-h/2)))
        self.sync_controls();self.host.persist_session()
    def full_bleed(self):
        l=self.selected()
        if not l:return
        l.c['fit']=True;l.resize_to(1920,1080);l.setPos(0,0)
        self.layers.remove(l);self.layers.append(l);self.refresh();self.list.setCurrentRow(len(self.layers)-1)
        self.sync_controls();self.host.persist_session()
        self.host.status.setText('已滿版：1920×1080，等比例填滿（超出部分裁切）；此畫面已移到最上層。')
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
        for i,l in enumerate(self.layers):
            l.resize_to(1920/cols,1080/rows);l.setPos((i%cols)*1920/cols,((i//cols)%rows)*1080/rows)
        self.sync_controls()
    def snapshot(self):return [deepcopy(l.c) for l in self.layers]
    def restore(self,layout):
        for l in self.layers:l.dispose();self.host.screen.scene().removeItem(l)
        self.layers=[];self.refresh()
        for c in layout:self.add(c)
    def remember(self):
        name,ok=QInputDialog.getText(self.host,'場景記憶','場景名稱')
        if ok and name.strip():self.scenes.append({'name':name.strip(),'layout':self.snapshot(),'settings':self.host.settings()});self.refresh_scenes();self.scene_list.setCurrentIndex(len(self.scenes)-1);self.host.persist_session()
    def refresh_scenes(self):self.scene_list.clear();self.scene_list.addItems([s['name'] for s in self.scenes])
    def recall(self):
        i=self.scene_list.currentIndex()
        if i<0:return
        s=self.scenes[i];self.stop();self.host.apply_settings(s.get('settings',{}));self.enable.setChecked(True);self.restore(s['layout']);self.host.status.setText('場景已載入；按播放啟動。')
    def overwrite(self):
        i=self.scene_list.currentIndex()
        if i>=0:self.scenes[i].update(layout=self.snapshot(),settings=self.host.settings());self.host.persist_session()
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

