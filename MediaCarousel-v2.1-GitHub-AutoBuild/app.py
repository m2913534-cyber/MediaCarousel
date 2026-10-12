import os, sys, time, random
os.environ.setdefault('QT_MEDIA_BACKEND','ffmpeg')
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl, QSizeF, QRectF, QStandardPaths
from PySide6.QtGui import QPixmap, QPainter, QShortcut, QKeySequence, QImageReader
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QPushButton,QLabel,QComboBox,QDoubleSpinBox,QSlider,QListWidget,QListWidgetItem,
    QFileDialog,QInputDialog,QMessageBox,QGraphicsScene,QGraphicsView,QGraphicsPixmapItem,QSplitter,QCheckBox)
from PySide6.QtMultimedia import QMediaPlayer,QAudioOutput,QMediaFormat
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from model import following, save_project, load_project, MODES, EFFECTS, IMAGE_EXT, clip_bounds

class Screen(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self)); self.setSceneRect(0,0,1920,1080)
        self.setBackgroundBrush(Qt.black); self.setFrameShape(QGraphicsView.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHints(QPainter.Antialiasing|QPainter.SmoothPixmapTransform)
        self.setWindowTitle('Media Carousel — 播放輸出'); self.resize(960,540)
        self.exit_callback=None
    def resizeEvent(self,event):
        super().resizeEvent(event); self.fitInView(self.sceneRect(),Qt.KeepAspectRatio)
    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Escape: self.showNormal()
        else: super().keyPressEvent(event)
    def closeEvent(self,event):
        if self.exit_callback: self.exit_callback()
        super().closeEvent(event)

class Deck:
    def __init__(self,screen):
        self.video=QGraphicsVideoItem(); self.video.setSize(QSizeF(1920,1080))
        self.image=QGraphicsPixmapItem(); screen.scene().addItem(self.video); screen.scene().addItem(self.image)
        self.audio=QAudioOutput(); self.player=QMediaPlayer(); self.player.setAudioOutput(self.audio); self.player.setVideoOutput(self.video)
        self.item=self.image; self.kind='image'; self.config={}; self.clip_loaded=False; self.clear()
    def clear(self):
        self.player.stop(); self.video.hide(); self.image.hide(); self.audio.setVolume(0)
    def load(self,path,fit,config=None):
        self.clear(); self.path=path; self.config=dict(config or {}); self.clip_loaded=False
        if Path(path).suffix.lower() in IMAGE_EXT:
            reader=QImageReader(path); reader.setAutoTransform(True); image=reader.read()
            if image.isNull(): raise ValueError('無法讀取圖片')
            self.kind='image'; self.item=self.image; self.image.setPixmap(QPixmap.fromImage(image))
            w,h=image.width(),image.height(); scale=(max if fit else min)(1920/w,1080/h)
            self.image.setScale(scale); self.image.setPos((1920-w*scale)/2,(1080-h*scale)/2)
        else:
            self.kind='video'; self.item=self.video; self.video.setScale(1); self.video.setPos(0,0)
            self.video.setAspectRatioMode(Qt.KeepAspectRatioByExpanding if fit else Qt.KeepAspectRatio)
            self.player.setSource(QUrl.fromLocalFile(path))
        self.item.setOpacity(0); self.item.show()
        self.basepos=self.item.pos(); self.basescale=self.item.scale()
        self.item.setTransformOriginPoint(self.item.boundingRect().center())

class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Media Carousel 2.0｜影音輪播工作台'); self.resize(1320,820)
        self.lists=[{'name':'播放清單 1','items':[]}]; self.current=None; self.active=0
        self.running=False; self.pending=None; self.transition=None; self.elapsed=0; self.failed=set()
        self.screen=Screen(); self.screen.exit_callback=self.stop; self.decks=[Deck(self.screen),Deck(self.screen)]
        for i,d in enumerate(self.decks):
            d.player.mediaStatusChanged.connect(lambda s,i=i:self.media_status(i,s))
            d.player.errorOccurred.connect(lambda e,m,i=i:self.media_error(i,m))
            d.video.videoSink().videoFrameChanged.connect(lambda f,i=i:self.first_frame(i,f))
        root=QWidget(); self.setCentralWidget(root); layout=QVBoxLayout(root)
        title=QLabel('MEDIA CAROUSEL   /   影音輪播工作台'); title.setStyleSheet('font-size:24px;font-weight:700;color:#6ee7d4;padding:14px'); layout.addWidget(title)
        tools=QHBoxLayout(); layout.addLayout(tools)
        for label,fn in [('開啟專案',self.open_project),('儲存專案',self.save),('新增清單',self.new_list),('重新命名',self.rename_list),('刪除清單',self.delete_list),('格式資訊',self.formats)]: self.button(tools,label,fn)
        split=QSplitter(); layout.addWidget(split,1)
        left=QWidget(); panel=QVBoxLayout(left); split.addWidget(left)
        self.groups=QComboBox(); self.groups.currentIndexChanged.connect(self.render); panel.addWidget(self.groups)
        self.files=QListWidget(); self.files.itemDoubleClicked.connect(lambda _:self.play_selected()); self.files.currentRowChanged.connect(self.selection); panel.addWidget(self.files,1)
        row=QHBoxLayout(); panel.addLayout(row)
        self.button(row,'加入影片／圖片',self.add_files); self.button(row,'移除',self.remove)
        row=QHBoxLayout(); panel.addLayout(row); self.button(row,'↑ 上移',lambda:self.move(-1)); self.button(row,'↓ 下移',lambda:self.move(1))
        row=QHBoxLayout(); panel.addLayout(row); row.addWidget(QLabel('所選圖片秒數'))
        self.seconds=QDoubleSpinBox(); self.seconds.setRange(.5,86400); self.seconds.setValue(5); self.seconds.setSuffix(' 秒'); self.seconds.valueChanged.connect(self.set_seconds); row.addWidget(self.seconds)
        self.button(panel,'套用秒數到本清單所有圖片',self.apply_seconds)
        panel.addWidget(QLabel('影片片段／聲音（保留原始檔案）'))
        row=QHBoxLayout();panel.addLayout(row);row.addWidget(QLabel('開始秒'))
        self.clip_start=QDoubleSpinBox();self.clip_start.setRange(0,86400);self.clip_start.setDecimals(2);row.addWidget(self.clip_start)
        row=QHBoxLayout();panel.addLayout(row);row.addWidget(QLabel('結束秒（0＝原片尾）'))
        self.clip_end=QDoubleSpinBox();self.clip_end.setRange(0,86400);self.clip_end.setDecimals(2);row.addWidget(self.clip_end)
        row=QHBoxLayout();panel.addLayout(row);row.addWidget(QLabel('單檔音量 %'))
        self.clip_gain=QDoubleSpinBox();self.clip_gain.setRange(0,100);self.clip_gain.setValue(100);row.addWidget(self.clip_gain)
        self.clip_mute=QCheckBox('單檔靜音');panel.addWidget(self.clip_mute)
        self.button(panel,'套用片段與音量',self.edit_clip)
        panel.addWidget(QLabel('GIF 目前顯示第一影格；片段設定不輸出新影片。'))
        right=QWidget(); controls=QVBoxLayout(right); split.addWidget(right); controls.addWidget(self.screen,1)
        row=QHBoxLayout(); controls.addLayout(row)
        self.button(row,'⏮ 上一個',lambda:self.advance(True)); self.play_btn=self.button(row,'▶ 播放／暫停',self.toggle); self.button(row,'■ 停止',self.stop); self.button(row,'下一個 ⏭',self.advance)
        self.button(row,'獨立輸出／全螢幕',self.output);self.button(row,'選擇輸出螢幕',self.choose_output)
        self.seek=QSlider(Qt.Horizontal); self.seek.setRange(0,1000); self.seek.sliderReleased.connect(self.seek_to); controls.addWidget(self.seek)
        row=QHBoxLayout(); controls.addLayout(row); row.addWidget(QLabel('輪播模式'))
        self.mode=QComboBox(); self.mode.addItems(MODES); row.addWidget(self.mode)
        self.effect=QComboBox(); self.effect.addItems(EFFECTS); row.addWidget(self.effect)
        self.duration=QDoubleSpinBox(); self.duration.setRange(.1,10); self.duration.setValue(1); self.duration.setSuffix(' 秒切換'); row.addWidget(self.duration)
        row=QHBoxLayout(); controls.addLayout(row); row.addWidget(QLabel('音量')); self.volume=QSlider(Qt.Horizontal); self.volume.setRange(0,100); self.volume.setValue(80); row.addWidget(self.volume)
        self.fit=QComboBox(); self.fit.addItems(['完整顯示（保留黑邊）','填滿畫面（裁切）']); row.addWidget(self.fit)
        self.status=QLabel('加入媒體後即可播放。可拖入檔案；Space 播放／暫停，F11 全螢幕，Esc 離開全螢幕。'); layout.addWidget(self.status)
        self.setAcceptDrops(True); split.setSizes([380,900]); self.refresh_groups()
        from compositor import Compositor
        self.compositor=Compositor(self)
        self.output_view=Screen();self.output_view.setScene(self.screen.scene());self.output_view.hide()
        self.timer=QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(16); self.last=time.monotonic()
        for key,fn in [('Space',self.toggle),('F11',self.output),('Right',self.advance),('Left',lambda:self.advance(True))]: QShortcut(QKeySequence(key),self,activated=fn)
        for key,fn in [('Space',self.toggle),('F11',self.output),('Right',self.advance),('Left',lambda:self.advance(True))]: QShortcut(QKeySequence(key),self.output_view,activated=fn)
        self.setStyleSheet('QWidget{background:#141e2c;color:#e8eff8;font-size:13px} QPushButton{background:#26364d;border:1px solid #3b516c;border-radius:6px;padding:9px} QPushButton:hover{background:#36526d} QListWidget,QComboBox,QDoubleSpinBox{background:#0d1623;border:1px solid #36465c;padding:6px} QListWidget::item{padding:10px} QListWidget::item:selected{background:#255f71} QSlider::handle:horizontal{background:#6ee7d4;width:14px;border-radius:7px}')
        self.session_path=Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))/'last-session.mcarousel'
        self.session_ready=False
        if self.session_path.exists():
            try:
                self.restore_project_data(load_project(self.session_path))
                self.status.setText('已恢復上次場景與播放清單；按播放啟動。')
            except Exception as exc:
                self.status.setText('上次場景讀取失敗，原檔保留：'+str(exc))
                return
        self.session_ready=True
        self.session_timer=QTimer(self);self.session_timer.timeout.connect(self.persist_session);self.session_timer.start(2000)
    def persist_session(self):
        if not self.session_ready:return
        try:
            self.session_path.parent.mkdir(parents=True,exist_ok=True)
            save_project(self.session_path,self.lists,self.settings(),self.compositor.scenes,self.compositor.snapshot())
        except Exception as exc:
            self.status.setText('自動保存失敗：'+str(exc))
    def restore_project_data(self,data):
        if not data['lists']:raise ValueError('專案沒有清單')
        self.stop();self.lists=data['lists'];self.refresh_groups();s=data.get('settings',{})
        self.apply_settings(s);self.compositor.scenes=data.get('scenes',[]);self.compositor.refresh_scenes();self.compositor.enable.setChecked(bool(s.get('multi',False)));self.compositor.restore(data.get('layout',[]))
    def button(self,row,label,fn):
        b=QPushButton(label); b.clicked.connect(lambda checked=False:fn()); row.addWidget(b); return b
    def group_index(self): return max(0,self.groups.currentIndex())
    def refresh_groups(self,index=0):
        self.groups.blockSignals(True); self.groups.clear(); self.groups.addItems([x['name'] for x in self.lists]); self.groups.setCurrentIndex(index); self.groups.blockSignals(False); self.render()
        if hasattr(self,'compositor'):self.compositor.refresh_groups()
    def render(self,*_):
        self.files.clear()
        for item in self.lists[self.group_index()]['items']:
            path=Path(item['path']); image=path.suffix.lower() in IMAGE_EXT
            text=f"{'圖片' if image else '影片'}  {path.name}"+ (f"  / {item['seconds']:g} 秒" if image else '')
            if not path.is_file(): text='⚠ 遺失  '+text
            self.files.addItem(text)
    def selection(self,row):
        items=self.lists[self.group_index()]['items']; self.seconds.blockSignals(True)
        if 0<=row<len(items):
            c=items[row];self.seconds.setValue(c['seconds']);self.clip_start.setValue(c.get('start',0));self.clip_end.setValue(c.get('end',0));self.clip_gain.setValue(c.get('gain',100));self.clip_mute.setChecked(c.get('mute',False))
        self.seconds.blockSignals(False)
    def edit_clip(self):
        row=self.files.currentRow();items=self.lists[self.group_index()]['items']
        if not 0<=row<len(items):return
        start,end=self.clip_start.value(),self.clip_end.value()
        if end and end<=start:QMessageBox.warning(self,'片段錯誤','結束秒數必須大於開始秒數');return
        self.stop();items[row].update(start=start,end=end,gain=self.clip_gain.value(),mute=self.clip_mute.isChecked())
        self.status.setText('片段與音量已套用；重新播放即可生效。')
    def set_seconds(self,value):
        row=self.files.currentRow(); items=self.lists[self.group_index()]['items']
        if 0<=row<len(items): items[row]['seconds']=value; self.render(); self.files.setCurrentRow(row)
    def apply_seconds(self):
        for item in self.lists[self.group_index()]['items']:
            if Path(item['path']).suffix.lower() in IMAGE_EXT: item['seconds']=self.seconds.value()
        self.render()
    def new_list(self):
        name,ok=QInputDialog.getText(self,'新增清單','清單名稱')
        if ok and name.strip(): self.lists.append({'name':name.strip(),'items':[]}); self.refresh_groups(len(self.lists)-1)
    def rename_list(self):
        name,ok=QInputDialog.getText(self,'重新命名','清單名稱',text=self.lists[self.group_index()]['name'])
        if ok and name.strip(): self.lists[self.group_index()]['name']=name.strip(); self.refresh_groups(self.group_index())
    def delete_list(self):
        if QMessageBox.question(self,'刪除清單','移除這份播放清單？原始媒體檔案會保留。')!=QMessageBox.Yes:return
        self.stop(); index=self.group_index(); self.lists.pop(index)
        if hasattr(self,'compositor'):
            for layout in [self.compositor.snapshot()]+[s['layout'] for s in self.compositor.scenes]:
                for c in layout:
                    if c.get('group',0)>index:c['group']-=1
                    elif c.get('group',0)==index:c['group']=0
            for l in self.compositor.layers:
                if l.c['group']>index:l.c['group']-=1
                elif l.c['group']==index:l.c['group']=0
        if not self.lists:self.lists=[{'name':'播放清單 1','items':[]}]
        self.refresh_groups()
    def add_files(self,paths=None):
        if paths is None: paths,_=QFileDialog.getOpenFileNames(self,'加入影片或圖片','','所有檔案 (*)')
        for path in paths:
            if Path(path).is_file(): self.lists[self.group_index()]['items'].append({'path':str(Path(path).resolve()),'seconds':self.seconds.value()})
        self.render()
    def remove(self):
        row=self.files.currentRow()
        if row>=0:self.stop(); self.lists[self.group_index()]['items'].pop(row); self.render()
    def move(self,delta):
        row=self.files.currentRow(); items=self.lists[self.group_index()]['items']; target=row+delta
        if row>=0 and 0<=target<len(items):self.stop(); items[row],items[target]=items[target],items[row]; self.render(); self.files.setCurrentRow(target)
    def play_selected(self):
        if hasattr(self,'compositor') and self.compositor.enabled:self.compositor.toggle();return
        self.failed.clear(); row=max(0,self.files.currentRow()); self.request((self.group_index(),row))
    def toggle(self):
        if hasattr(self,'compositor') and self.compositor.enabled:self.compositor.toggle();return
        if self.current is None:self.play_selected();return
        self.running=not self.running
        for i,d in enumerate(self.decks):
            if d.kind=='video' and (i==self.active or self.transition or self.pending):
                d.player.play() if self.running else d.player.pause()
        self.status.setText('播放中' if self.running else '已暫停')
    def stop(self):
        if hasattr(self,'compositor'):self.compositor.stop()
        self.stop_single()
    def stop_single(self):
        self.running=False; self.pending=None; self.transition=None; self.current=None; self.elapsed=0
        for d in self.decks:d.clear()
        self.seek.setValue(0); self.status.setText('已停止')
    def request(self,target):
        if target is None:self.stop();return
        p,i=target
        if not (0<=p<len(self.lists) and 0<=i<len(self.lists[p]['items'])):return
        if self.pending or self.transition:return
        self.current=target; self.groups.setCurrentIndex(p); self.files.setCurrentRow(i)
        item=self.lists[p]['items'][i]; idx=1-self.active; self.running=True
        self.pending={'index':idx,'started':time.monotonic()}; self.elapsed=0
        try:
            if not Path(item['path']).is_file():raise ValueError('找不到檔案')
            self.decks[idx].load(item['path'],self.fit.currentIndex()==1,item)
            if self.decks[idx].kind=='image':self.begin_transition()
            else:self.decks[idx].player.play()
        except Exception as e:self.fail(str(e))
    def first_frame(self,index,frame):
        if frame.isValid() and self.pending and index==self.pending['index']:QTimer.singleShot(0,self.begin_transition)
    def media_status(self,index,status):
        d=self.decks[index]
        if status==QMediaPlayer.LoadedMedia and not d.clip_loaded:
            d.clip_loaded=True;QTimer.singleShot(0,lambda d=d:d.player.setPosition(clip_bounds(d.config,d.player.duration())[0]))
        if status==QMediaPlayer.EndOfMedia and index==self.active and not self.pending and not self.transition and self.running:self.advance()
    def media_error(self,index,message):
        if (self.pending and index==self.pending['index']) or (index==self.active and self.current):self.fail(message)
    def fail(self,message):
        if self.current:self.failed.add(self.current)
        self.status.setText('無法播放：'+message+'。已停止，請移除此檔案或轉檔後重試。')
        self.pending=None; self.transition=None; self.running=False
        for d in self.decks:d.player.pause()
    def begin_transition(self):
        if not self.pending:return
        idx=self.pending['index']; self.pending=None
        effect=self.effect.currentText()
        if effect=='隨機效果':effect=random.choice(EFFECTS[:-1])
        self.decks[idx].item.setZValue(2); self.decks[self.active].item.setZValue(1)
        self.transition={'new':idx,'old':self.active,'time':0.,'effect':effect}
        self.elapsed=0; self.status.setText('播放中：'+Path(self.decks[idx].path).name)
        if effect=='直接切換':self.update_transition(1)
    def update_transition(self,t):
        tr=self.transition
        if not tr:return
        a=self.decks[tr['old']]; b=self.decks[tr['new']]; effect=tr['effect']
        old,new=1-t,t
        if effect=='淡出至黑再淡入':old=max(0,1-2*t);new=max(0,2*t-1)
        if effect=='直接切換':old,new=0,1
        # Incoming transparency reveals outgoing media; outgoing remains opaque for a true dissolve.
        a.item.setOpacity(old if effect=='淡出至黑再淡入' else 1); b.item.setOpacity(new)
        if effect in ('向左滑動','向右滑動'):
            offset=(1-t)*1920*(1 if effect=='向左滑動' else -1); b.item.setPos(b.basepos.x()+offset,b.basepos.y())
        if effect=='縮放淡入':b.item.setScale(b.basescale*(.85+.15*t))
        a.audio.setVolume(old*self.volume.value()/100*self.deck_gain(a)); b.audio.setVolume(new*self.volume.value()/100*self.deck_gain(b))
        if t>=1:
            a.clear(); b.item.setPos(b.basepos); b.item.setScale(b.basescale); b.item.setOpacity(1)
            self.active=tr['new']; self.transition=None
    def deck_gain(self,d):return 0 if d.config.get('mute') else d.config.get('gain',100)/100
    def advance(self,reverse=False):
        if hasattr(self,'compositor') and self.compositor.enabled:self.compositor.advance(reverse);return
        if self.pending or self.transition:return
        target=following(self.lists,self.current or (self.group_index(),-1),self.mode.currentText(),reverse)
        self.request(target)
    def tick(self):
        now=time.monotonic(); dt=min(now-self.last,.25); self.last=now
        if not self.running:return
        if self.pending:
            if now-self.pending['started']>20:self.fail('解碼逾時（20 秒）')
            return
        if self.transition:
            self.transition['time']+=dt; self.update_transition(min(1,self.transition['time']/self.duration.value()));return
        if self.current is None:return
        d=self.decks[self.active]; item=self.lists[self.current[0]]['items'][self.current[1]]
        d.audio.setVolume(self.volume.value()/100*self.deck_gain(d))
        if d.kind=='image':
            self.elapsed+=dt; fraction=self.elapsed/item['seconds']
            if fraction>=1:self.advance()
        else:
            if d.player.mediaStatus()==QMediaPlayer.EndOfMedia:
                self.advance();return
            start,end=clip_bounds(d.config,d.player.duration());duration=end-start
            fraction=(d.player.position()-start)/duration if duration else 0
            if end and d.player.position()>=end:self.advance();return
            # Start overlap only near the end; short videos use their end-of-media event.
            remaining=end-d.player.position()
            if duration>self.duration.value()*2000 and 0<remaining<=self.duration.value()*1000 and self.effect.currentText()!='直接切換':
                if following(self.lists,self.current,self.mode.currentText()) is not None:self.advance()
        if not self.seek.isSliderDown():self.seek.setValue(int(min(1,fraction)*1000))
    def seek_to(self):
        if self.current is None or self.pending or self.transition:return
        d=self.decks[self.active]
        if d.kind=='video':
            start,end=clip_bounds(d.config,d.player.duration());d.player.setPosition(start+int((end-start)*self.seek.value()/1000))
        else:self.elapsed=self.lists[self.current[0]]['items'][self.current[1]]['seconds']*self.seek.value()/1000
    def output(self):
        self.compositor.edit.setChecked(False)
        if self.output_view.isFullScreen():self.output_view.showNormal()
        else:self.output_view.showFullScreen()
    def choose_output(self):
        screens=QApplication.screens();labels=[f'{i+1}. {s.name()} / {s.size().width()}×{s.size().height()}' for i,s in enumerate(screens)]
        label,ok=QInputDialog.getItem(self,'選擇輸出螢幕','螢幕',labels,0,False)
        if ok:
            screen=screens[labels.index(label)];self.output_view.showNormal();self.output_view.windowHandle().setScreen(screen);self.output_view.setGeometry(screen.geometry());self.output()
    def settings(self):return {'mode':self.mode.currentText(),'effect':self.effect.currentText(),'duration':self.duration.value(),'volume':self.volume.value(),'fit':self.fit.currentIndex(),'multi':getattr(self,'compositor',None) is not None and self.compositor.enabled}
    def save(self):
        path,_=QFileDialog.getSaveFileName(self,'儲存輪播專案','','輪播專案 (*.mcarousel)')
        if path:
            if not path.endswith('.mcarousel'):path+='.mcarousel'
            try:save_project(path,self.lists,self.settings(),self.compositor.scenes,self.compositor.snapshot());self.status.setText('專案已儲存；媒體檔案需另外保留。')
            except Exception as e:QMessageBox.warning(self,'儲存失敗',str(e))
    def open_project(self):
        path,_=QFileDialog.getOpenFileName(self,'開啟輪播專案','','輪播專案 (*.mcarousel)')
        if not path:return
        try:
            data=load_project(path)
            self.restore_project_data(data)
            self.session_ready=True;self.persist_session()
        except Exception as e:QMessageBox.warning(self,'開啟失敗',str(e))
    def apply_settings(self,s):
        self.mode.setCurrentText(s.get('mode',MODES[0]));self.effect.setCurrentText(s.get('effect',EFFECTS[0]));self.duration.setValue(float(s.get('duration',1)));self.volume.setValue(int(s.get('volume',80)));self.fit.setCurrentIndex(int(s.get('fit',0)))
    def formats(self):
        fmt=QMediaFormat();formats=fmt.supportedFileFormats(QMediaFormat.Decode);codecs=fmt.supportedVideoCodecs(QMediaFormat.Decode)
        QMessageBox.information(self,'這台電腦的解碼能力','封裝格式：\n'+', '.join(QMediaFormat.fileFormatName(f) for f in formats)+'\n\n影片編碼：\n'+', '.join(QMediaFormat.videoCodecName(c) for c in codecs)+'\n\n副檔名不代表編碼。受 DRM 保護、損壞或未支援的編碼無法保證播放。')
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls():e.acceptProposedAction()
    def dropEvent(self,e):self.add_files([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])
    def closeEvent(self,e):self.persist_session();self.screen.scene().selectionChanged.disconnect(self.compositor.scene_selection);self.stop();self.screen.exit_callback=None;self.screen.close();self.output_view.close();super().closeEvent(e)

if __name__=='__main__':
    app=QApplication(sys.argv);app.setApplicationName('Media Carousel');window=Window();window.show()
    if '--build-smoke-test' in sys.argv:
        import json
        report=Path(sys.argv[sys.argv.index('--build-smoke-test')+1])
        def finish_smoke():
            codecs=QMediaFormat().supportedVideoCodecs(QMediaFormat.Decode)
            ok=window.isVisible() and bool(QApplication.screens()) and bool(codecs)
            report.write_text(json.dumps({'ok':ok,'video_codecs':len(codecs)}),encoding='utf-8')
            window.close();app.exit(0 if ok else 1)
        QTimer.singleShot(1500,finish_smoke)
    sys.exit(app.exec())
