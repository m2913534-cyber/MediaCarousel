import os, sys, time, random, json
from copy import deepcopy
if '--build-smoke-test' in sys.argv:
    def smoke_exception(kind,value,tb):
        import traceback
        report=sys.argv[sys.argv.index('--build-smoke-test')+1]
        with open(report,'w',encoding='utf-8') as stream:json.dump({'ok':False,'error':''.join(traceback.format_exception(kind,value,tb))},stream)
        os._exit(1)
    sys.excepthook=smoke_exception
os.environ.setdefault('QT_MEDIA_BACKEND','ffmpeg')
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl, QSizeF, QRectF, QStandardPaths
from PySide6.QtGui import QTransform,QPen,QPixmap, QPainter, QShortcut, QKeySequence, QImageReader
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QPushButton,QLabel,QComboBox,QDoubleSpinBox,QSlider,QListWidget,QListWidgetItem,
    QFileDialog,QInputDialog,QMessageBox,QGraphicsScene,QGraphicsView,QGraphicsPixmapItem,QSplitter,QCheckBox,QGraphicsRectItem,QGraphicsItem)
from PySide6.QtMultimedia import QMediaPlayer,QAudioOutput,QMediaFormat
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from model import following, save_project, load_project, MODES, EFFECTS, IMAGE_EXT, clip_bounds, is_still, media_name,is_pdf,is_powerpoint,single_transform

class Screen(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self)); self.setSceneRect(0,0,1920,1080)
        self.canvas_root=QGraphicsRectItem(0,0,1920,1080);self.canvas_root.setPen(QPen(Qt.NoPen));self.canvas_root.setBrush(Qt.black);self.canvas_root.setFlag(QGraphicsItem.ItemClipsChildrenToShape);self.scene().addItem(self.canvas_root)
        self.setBackgroundBrush(Qt.black); self.setFrameShape(QGraphicsView.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHints(QPainter.Antialiasing|QPainter.SmoothPixmapTransform)
        self.setWindowTitle('Media Carousel — 播放輸出'); self.resize(960,540)
        self.exit_callback=None;self.fit_mode=0
    def refit(self):
        r=self.sceneRect();v=self.viewport().size()
        if not r.width() or not r.height():return
        sx,sy=v.width()/r.width(),v.height()/r.height()
        if self.fit_mode!=2:sx=sy=(max if self.fit_mode==1 else min)(sx,sy)
        self.resetTransform();self.scale(sx,sy);self.centerOn(r.center())
    def resizeEvent(self,event):
        super().resizeEvent(event); self.refit()
    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Escape: self.showNormal()
        else: super().keyPressEvent(event)
    def closeEvent(self,event):
        if self.exit_callback: self.exit_callback()
        super().closeEvent(event)

class Deck:
    def __init__(self,screen):
        self.screen=screen;self.root=QGraphicsRectItem(screen.canvas_root);self.root.setPen(QPen(Qt.NoPen));self.last_frame=None;self.video=QGraphicsVideoItem(self.root); self.video.setSize(QSizeF(1920,1080))
        self.image=QGraphicsPixmapItem(self.root)
        self.audio=QAudioOutput(); self.player=QMediaPlayer();
        from live_audio import LiveAudio
        self.live_audio=LiveAudio(self.audio)
        from playback_cache import Preroll
        self.preroll=Preroll(self.player)
        from audio_meter import AudioProbe
        self.probe=AudioProbe(self.player); self.player.setAudioOutput(self.audio); self.player.setVideoOutput(self.video)
        self.video.videoSink().videoFrameChanged.connect(self.remember_frame)
        from pdf_source import PdfSource
        self.pdf_source=PdfSource();self.pdf_source.ready.connect(self.pdf_ready)
        self.item=self.image; self.kind='image'; self.config={}; self.clip_loaded=False; self.clear()
    def pdf_ready(self,image,page,count):
        self.image.setPixmap(QPixmap.fromImage(image));self.config['pdf_page']=page;self.relayout(self.fit_mode)
    def remember_frame(self,frame):
        if self.preroll.observe(frame):self.last_frame=frame
    def freeze(self):
        self.player.pause()
        if self.kind=='video' and self.last_frame is not None:
            self.image.setPixmap(QPixmap.fromImage(self.last_frame.toImage()));self.image.setPos(self.video.pos());self.image.setZValue(self.video.zValue())
            self.kind='image';self.item=self.image;self.video.hide();self.relayout(self.fit_mode);self.image.setOpacity(1);self.image.show()
    def clear(self):
        self.load_generation=getattr(self,'load_generation',0)+1;self.preroll.reset();self.source_ref=None;self.pdf_source.close();self.last_frame=None;self.player.stop(); self.video.hide(); self.image.hide(); self.live_audio.apply(0,False)
    def resume_position(self,generation):
        if generation!=self.load_generation:return
        start,end=clip_bounds(self.config,self.player.duration());target=max(start,min(self.config.pop('_resume_ms',0),max(0,end-1)))
        if target>0:self.player.setPosition(target)
        self.preroll.positioned_at(target)
    def load(self,path,fit,config=None,warm=False):
        self.clear();self.preroll.warming=warm; self.path=path;self.source_ref=config; self.config=dict(config or {}); self.clip_loaded=False
        if is_pdf(self.config):
            self.kind='pdf';self.item=self.image;self.fit_mode=int(fit);self.pdf_source.load(path,self.config.get('pdf_page',0),self.screen.sceneRect().size().toSize())
        elif self.config.get('kind')=='black':
            self.kind='image';self.item=self.image;pix=QPixmap(2,2);pix.fill(Qt.black);self.image.setPixmap(pix)
        elif Path(path).suffix.lower() in IMAGE_EXT:
            reader=QImageReader(path); reader.setAutoTransform(True); image=reader.read()
            if image.isNull(): raise ValueError('無法讀取圖片')
            self.kind='image'; self.item=self.image; self.image.setPixmap(QPixmap.fromImage(image))
            w,h=image.width(),image.height(); scale=(max if fit else min)(self.screen.sceneRect().width()/w,self.screen.sceneRect().height()/h)
            self.image.setScale(scale); self.image.setPos((self.screen.sceneRect().width()-w*scale)/2,(self.screen.sceneRect().height()-h*scale)/2)
        else:
            self.kind='video'; self.item=self.video; self.video.setScale(1); self.video.setPos(0,0)
            self.video.setSize(self.screen.sceneRect().size());self.video.setAspectRatioMode(Qt.KeepAspectRatioByExpanding if fit else Qt.KeepAspectRatio)
            url=QUrl.fromLocalFile(path);same=self.player.source()==url
            if same and self.player.error()!=QMediaPlayer.NoError:self.player.setSource(QUrl());same=False
            self.player.setSource(url)
            if same and self.player.duration()>0:
                self.clip_loaded=True;generation=self.load_generation;QTimer.singleShot(0,lambda:self.resume_position(generation))
        self.relayout(fit);self.item.setOpacity(0); self.item.show()
        self.basepos=self.item.pos(); self.basescale=self.item.scale()
        self.item.setTransformOriginPoint(0,0)

    def apply_transform(self):
        r=self.screen.sceneRect();x,y,sx,sy=single_transform(self.config);self.root.setPos(x*r.width(),y*r.height());self.root.setScale(1);self.root.setTransform(QTransform.fromScale(sx,sy))
    def relayout(self,fit):
        self.fit_mode=int(fit);self.item.setTransformOriginPoint(0,0);cw,ch=self.screen.sceneRect().width(),self.screen.sceneRect().height()
        self.image.setTransform(QTransform());self.image.setScale(1)
        if self.kind in ('image','pdf') and not self.image.pixmap().isNull():
            w,h=self.image.boundingRect().width(),self.image.boundingRect().height()
            if fit==2:self.image.setTransform(QTransform.fromScale(cw/w,ch/h));self.image.setPos(0,0)
            else:
                scale=(max if fit else min)(cw/w,ch/h);self.image.setScale(scale);self.image.setPos((cw-w*scale)/2,(ch-h*scale)/2)
        else:
            self.video.setSize(self.screen.sceneRect().size());self.video.setAspectRatioMode([Qt.KeepAspectRatio,Qt.KeepAspectRatioByExpanding,Qt.IgnoreAspectRatio][int(fit)])
        self.basepos=self.item.pos();self.basescale=self.item.scale();self.apply_transform()

class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Media Carousel 2.10｜影音輪播工作台'); self.resize(1320,820)
        self.cue_item=None;self.lists=[{'name':'播放清單 1','items':[]}]; self.current=None; self.active=0
        self.held=False;self.running=False; self.pending=None; self.transition=None; self.elapsed=0; self.failed=set()
        self.screen=Screen(); self.screen.exit_callback=self.stop; self.decks=[Deck(self.screen),Deck(self.screen)]
        for i,d in enumerate(self.decks):
            d.pdf_source.ready.connect(lambda image,page,total,i=i:self.document_ready(i,page,total))
            d.pdf_source.failed.connect(lambda message,i=i:self.media_error(i,message))
            d.player.mediaStatusChanged.connect(lambda s,i=i:self.media_status(i,s))
            d.player.errorOccurred.connect(lambda e,m,i=i:self.media_error(i,m))
            d.video.videoSink().videoFrameChanged.connect(lambda f,i=i:self.first_frame(i,f))
        from interface import Interface
        self.interface=Interface(self);self.refresh_groups()
        from compositor import Compositor
        self.compositor=Compositor(self);self.interface.finish(self.compositor)
        from single_editor import SingleEditor
        self.single_editor=SingleEditor(self)
        self.output_view=Screen();self.output_view.viewport().setProperty('clean_output',True);self.output_view.setInteractive(False);self.output_view.setScene(self.screen.scene());self.output_view.hide();self.refresh_output_fit()
        self.preview_view=Screen();self.preview_view.viewport().setProperty('clean_output',True);self.preview_view.setInteractive(False);self.preview_view.setScene(self.screen.scene());self.preview_view.setWindowTitle('即時預覽 — Media Carousel');self.preview_view.resize(800,450);self.preview_view.hide()
        from presentations import PresentationController
        self.presentations=PresentationController(self)
        from playback_cache import NextVideoCache
        self.next_cache=NextVideoCache(self)
        self.volume.valueChanged.connect(self.refresh_live_audio)
        self.clip_gain.valueChanged.connect(lambda value:self.live_selected_audio(gain=value))
        self.clip_mute.toggled.connect(lambda value:self.live_selected_audio(mute=value))
        self.timer=QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(16); self.last=time.monotonic()
        for key,fn in [('Space',self.toggle),('F11',self.output),('Right',self.advance),('Left',lambda:self.advance(True))]: QShortcut(QKeySequence(key),self,activated=fn)
        for key,fn in [('Space',self.toggle),('F11',self.output),('Right',self.advance),('Left',lambda:self.advance(True))]: QShortcut(QKeySequence(key),self.output_view,activated=fn)
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
            state=json.dumps([self.lists,self.settings(),self.compositor.scenes,self.compositor.snapshot()],ensure_ascii=False,sort_keys=True)
            if state==getattr(self,'_saved_state',None):return
            save_project(self.session_path,self.lists,self.settings(),self.compositor.scenes,self.compositor.snapshot());self._saved_state=state
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
            path=Path(item['path']); image=is_still(item)
            text=f"{'PDF' if is_pdf(item) else 'PowerPoint' if is_powerpoint(item) else '黑畫面' if item.get('kind')=='black' else '圖片' if image else '影片'}  {media_name(item)}"+ (f"  / {item['seconds']:g} 秒" if image else '')
            if item.get('kind')!='black' and not path.is_file(): text='⚠ 遺失  '+text
            self.files.addItem(text)
    def selection(self,row):
        items=self.lists[self.group_index()]['items']; self.seconds.blockSignals(True);self.clip_gain.blockSignals(True);self.clip_mute.blockSignals(True)
        if 0<=row<len(items):
            c=items[row];self.seconds.setValue(c['seconds']);self.clip_start.setValue(c.get('start',0));self.clip_end.setValue(c.get('end',0));self.clip_gain.setValue(c.get('gain',100));self.clip_mute.setChecked(c.get('mute',False))
        self.seconds.blockSignals(False);self.clip_gain.blockSignals(False);self.clip_mute.blockSignals(False)
    def sync_selected_audio(self):
        row=self.files.currentRow();items=self.lists[self.group_index()]['items']
        if not 0<=row<len(items):return
        self.clip_gain.blockSignals(True);self.clip_mute.blockSignals(True);self.clip_gain.setValue(items[row].get('gain',100));self.clip_mute.setChecked(items[row].get('mute',False));self.clip_gain.blockSignals(False);self.clip_mute.blockSignals(False)
    def live_selected_audio(self,gain=None,mute=None):
        row=self.files.currentRow();items=self.lists[self.group_index()]['items']
        if not 0<=row<len(items):return
        source=items[row];changes={}
        if gain is not None:changes['gain']=gain
        if mute is not None:changes['mute']=bool(mute)
        source.update(changes)
        decks=list(self.decks)+[d for l in self.compositor.layers for d in l.decks]
        for d in decks:
            if d.source_ref is source:d.config.update(changes)
        self.refresh_live_audio();self.persist_session()
    def refresh_live_audio(self,*_):
        self.apply_audio()
        for layer in self.compositor.layers:layer.apply_audio()
    def apply_audio(self,progress=None):
        envelopes=[0.,0.]
        if self.transition:
            tr=self.transition;t=max(0,min(1,progress if progress is not None else tr['time']/self.duration.value()))
            old,new=(max(0,1-2*t),max(0,2*t-1)) if tr['effect']=='淡出至黑再淡入' else (1-t,t)
            if tr['effect']=='直接切換':old,new=0,1
            envelopes[tr['old']],envelopes[tr['new']]=old,new
        elif self.current is not None:envelopes[self.active]=1
        for i,d in enumerate(self.decks):
            d.live_audio.apply(envelopes[i]*self.volume.value()/100*self.deck_gain(d),d.config.get('mute'))
    def show_preview(self):
        self.preview_view.show();self.preview_view.raise_();self.preview_view.refit()
    def media_menu(self,pos):
        row=self.files.indexAt(pos).row()
        if row<0:return
        self.files.setCurrentRow(row)
        item=self.lists[self.group_index()]['items'][row]
        if is_pdf(item) or is_powerpoint(item):
            from PySide6.QtWidgets import QMenu
            menu=QMenu(self);play=menu.addAction('播放 PDF' if is_pdf(item) else 'PowerPoint 原生放映')
            if menu.exec(self.files.viewport().mapToGlobal(pos))==play:self.play_selected()
            return
        if is_still(item):return
        from PySide6.QtWidgets import QMenu
        menu=QMenu(self);action=menu.addAction('編輯影片…')
        if menu.exec(self.files.viewport().mapToGlobal(pos))==action:self.open_video_editor(row)
    def open_video_editor(self,row):
        from video_editor import VideoEditor
        items=self.lists[self.group_index()]['items']
        if not 0<=row<len(items):return
        item=items[row]
        if not Path(item['path']).is_file():QMessageBox.warning(self,'檔案遺失','請重新加入影片。');return
        if not hasattr(self,'video_editors'):self.video_editors={}
        key=id(item)
        if key in self.video_editors:
            self.video_editors[key].show();self.video_editors[key].raise_();return
        dialog=VideoEditor(item['path'],item,self);dialog.setAttribute(Qt.WA_DeleteOnClose);self.video_editors[key]=dialog
        def apply_edit():
            if not dialog.result_config:return
            if not any(item is source for group in self.lists for source in group['items']):
                self.status.setText('原列表來源已移除，這次編輯未套用。');return
            # Update the saved source. Running decks keep their current playback configuration.
            item.update(dialog.result_config)
            selected=self.files.currentRow();self.render();self.files.setCurrentRow(selected);self.persist_session()
            self.status.setText('編輯已儲存；目前輸出持續播放，重新播放或重新套用來源時生效。')
        dialog.accepted.connect(apply_edit);dialog.finished.connect(lambda _:self.video_editors.pop(key,None));dialog.show()
    def edit_clip(self):
        row=self.files.currentRow();items=self.lists[self.group_index()]['items']
        if not 0<=row<len(items):return
        start,end=self.clip_start.value(),self.clip_end.value()
        if end and end<=start:QMessageBox.warning(self,'片段錯誤','結束秒數必須大於開始秒數');return
        items[row].update(start=start,end=end,gain=self.clip_gain.value(),mute=self.clip_mute.isChecked())
        self.live_selected_audio(gain=self.clip_gain.value(),mute=self.clip_mute.isChecked());self.status.setText('音量與靜音即時生效；片段起訖在下次播放時套用。')
    def set_seconds(self,value):
        row=self.files.currentRow(); items=self.lists[self.group_index()]['items']
        if 0<=row<len(items): items[row]['seconds']=value; self.render(); self.files.setCurrentRow(row)
    def apply_seconds(self):
        for item in self.lists[self.group_index()]['items']:
            if is_still(item) or is_pdf(item): item['seconds']=self.seconds.value()
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
    def add_black(self):
        self.lists[self.group_index()]['items'].append({'kind':'black','path':'media:black','name':'黑畫面','seconds':self.seconds.value(),'start':0,'end':0,'gain':0,'mute':True})
        self.render();self.files.setCurrentRow(len(self.lists[self.group_index()]['items'])-1);self.persist_session()
    def add_files(self,paths=None):
        if paths is None: paths,_=QFileDialog.getOpenFileNames(self,'加入影片、圖片或簡報','','媒體與簡報 (*.pdf *.ppt *.pptx *.pps *.ppsx *.mp4 *.mov *.mkv *.avi *.webm *.m4v *.mp3 *.wav *.jpg *.jpeg *.png *.webp *.bmp *.gif *.tif *.tiff);;所有檔案 (*)')
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
        if hasattr(self,'compositor') and self.compositor.enabled:self.compositor.use_selected_file();return
        self.failed.clear(); row=max(0,self.files.currentRow()); self.request((self.group_index(),row))
    def free_transform(self):
        if self.presentations.active:self.status.setText('PowerPoint 以原生簡報比例獨立放映；PDF 可在畫布拖曳縮放。');return
        if self.compositor.enabled:
            self.status.setText('自由影像縮放僅用於單畫面；多畫面請拖曳格子，內容會保持填滿。');return
        self.single_editor.enabled=not self.single_editor.enabled
        if self.single_editor.enabled and self.current is None:
            if self.files.currentRow()<0:
                self.single_editor.enabled=False;self.status.setText('請先在左側選取檔案');return
            self.play_selected()
        self.single_editor.sync()
        self.status.setText('單畫面編輯：四邊獨立調整寬高，四角自由拉伸；拖曳中央移動。一鍵滿版可重設。' if self.single_editor.enabled else '已關閉單畫面拖曳縮放')
    def toggle(self):
        if self.presentations.active:self.presentations.command('pause');return
        if hasattr(self,'compositor') and self.compositor.enabled:self.compositor.toggle();return
        if self.held:self.request(self.current,item_override=self.cue_item);return
        if self.current is None:self.play_selected();return
        self.running=not self.running
        for i,d in enumerate(self.decks):
            if d.kind=='video' and (i==self.active or self.transition or self.pending):
                d.player.play() if self.running else d.player.pause()
        self.status.setText('播放中' if self.running else '已暫停')
    def stop(self):
        if hasattr(self,'presentations'):self.presentations.stop()
        if hasattr(self,'compositor'):self.compositor.stop()
        self.stop_single()
    def stop_single(self):
        if hasattr(self,'next_cache'):self.next_cache.discard(self,clear=False)
        self.cue_item=None;self.held=False;self.running=False; self.pending=None; self.transition=None; self.current=None; self.elapsed=0
        for d in self.decks:d.clear()
        self.seek.setValue(0); self.status.setText('已停止')
        if hasattr(self,'single_editor'):self.single_editor.sync()
    def current_item(self):
        return self.cue_item if self.cue_item is not None else self.lists[self.current[0]]['items'][self.current[1]]
    def request(self,target,item_override=None):
        if target is None:
            if self.hold_last.isChecked() and self.current is not None:
                self.held=True;self.running=False;self.decks[self.active].freeze();self.status.setText('播放結束：停留最後一幀')
            else:self.stop();self.status.setText('播放結束：影像已消失')
            return
        p,i=target
        candidate=item_override if item_override is not None else (self.lists[p]['items'][i] if 0<=p<len(self.lists) and 0<=i<len(self.lists[p]['items']) else None)
        if candidate is not None and is_powerpoint(candidate):
            self.presentations.start_native(target,candidate,item_override is not None);return
        if self.presentations.active or self.presentations.starting:self.presentations.stop()
        self.held=False
        if item_override is None and not (0<=p<len(self.lists) and 0<=i<len(self.lists[p]['items'])):return
        if self.pending or self.transition:return
        item=item_override if item_override is not None else self.lists[p]['items'][i]
        prepared=self.next_cache.take(self,target,item)
        self.current=target;self.cue_item=deepcopy(item_override) if item_override is not None else None
        if item_override is None:self.groups.setCurrentIndex(p);self.files.setCurrentRow(i)
        item=self.current_item(); idx=1-self.active; self.running=True
        self.pending={'index':idx,'started':time.monotonic()}; self.elapsed=0;self.single_editor.sync()
        try:
            if item.get('kind')!='black' and not Path(item['path']).is_file():raise ValueError('找不到檔案')
            d=self.decks[idx]
            if prepared is d:
                d.config=dict(item);d.source_ref=item;d.relayout(self.fit.currentIndex());d.item.setOpacity(0);d.item.show();d.preroll.activate()
                if d.preroll.ready:self.begin_transition()
            else:
                d.load(item['path'],self.fit.currentIndex(),item)
                if d.kind=='image':self.begin_transition()
                elif d.kind=='video':d.player.play()
        except Exception as e:self.fail(str(e))
    def document_ready(self,index,page,total):
        if self.pending and index==self.pending['index']:self.begin_transition()
        elif index==self.active and self.current is not None:
            self.current_item()['pdf_page']=page;self.elapsed=0
        if index==self.active and self.current is not None:self.current_item()['pdf_page']=page
    def first_frame(self,index,frame):
        if frame.isValid() and self.decks[index].preroll.ready and self.pending and index==self.pending['index']:
            generation=self.decks[index].load_generation
            QTimer.singleShot(0,lambda:self.begin_video_transition(index,generation))
    def begin_video_transition(self,index,generation):
        if self.pending and index==self.pending['index'] and generation==self.decks[index].load_generation:self.begin_transition()
    def media_status(self,index,status):
        d=self.decks[index]
        if status==QMediaPlayer.LoadedMedia and not d.clip_loaded:
            d.clip_loaded=True;generation=d.load_generation;QTimer.singleShot(0,lambda d=d,generation=generation:d.resume_position(generation))
        if status==QMediaPlayer.EndOfMedia and index==self.active and not self.pending and not self.transition and self.running:self.advance()
    def media_error(self,index,message):
        if self.decks[index].preroll.warming:self.decks[index].preroll.failed=True;return
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
        self.decks[idx].root.setZValue(2);self.decks[self.active].root.setZValue(1);self.decks[idx].item.setZValue(2); self.decks[self.active].item.setZValue(1)
        self.transition={'new':idx,'old':self.active,'time':0.,'effect':effect}
        self.elapsed=0; self.status.setText('播放中：'+media_name(self.decks[idx].config))
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
            offset=(1-t)*self.screen.sceneRect().width()*(1 if effect=='向左滑動' else -1); b.item.setPos(b.basepos.x()+offset,b.basepos.y())
        if effect=='縮放淡入':b.item.setScale(b.basescale*(.85+.15*t))
        self.apply_audio(t)
        if t>=1:
            a.clear(); b.item.setPos(b.basepos); b.item.setScale(b.basescale); b.item.setOpacity(1)
            self.active=tr['new']; self.transition=None;self.single_editor.sync()
    def deck_gain(self,d):return 0 if d.config.get('mute') else d.config.get('gain',100)/100
    def advance(self,reverse=False):
        if self.presentations.active:self.presentations.command('previous' if reverse else 'next');return
        if not self.compositor.enabled and self.current is not None and not self.pending and not self.transition:
            d=self.decks[self.active]
            if d.kind=='pdf' and d.pdf_source.step(reverse):self.elapsed=0;return
        self.advance_media(reverse)
    def advance_media(self,reverse=False):
        if hasattr(self,'compositor') and self.compositor.enabled:self.compositor.advance(reverse);return
        if self.pending or self.transition:return
        if self.cue_item is not None:
            target=following([{'items':[self.cue_item]}],(0,0),self.mode.currentText(),reverse)
            d=self.decks[self.active]
            if target is not None and self.effect.currentText()=='直接切換' and d.kind=='video' and not self.held:
                self.elapsed=0;d.player.setPosition(clip_bounds(d.config,d.player.duration())[0]);d.player.play();return
            item=deepcopy(self.cue_item);item.pop('_resume_ms',None);self.request(target,item_override=item);return
        target=following(self.lists,self.current or (self.group_index(),-1),self.mode.currentText(),reverse)
        if target==self.current and self.effect.currentText()=='直接切換' and not self.held:
            d=self.decks[self.active]
            if d.kind=='video':
                self.elapsed=0;d.player.setPosition(clip_bounds(d.config,d.player.duration())[0]);d.player.play();return
        self.request(target)
    def tick(self):
        now=time.monotonic(); dt=min(now-self.last,.25); self.last=now
        if self.presentations.active:return
        if not self.running:return
        if self.pending:
            if now-self.pending['started']>20:self.fail('解碼逾時（20 秒）')
            return
        if self.transition:
            self.transition['time']+=dt; self.update_transition(min(1,self.transition['time']/self.duration.value()));return
        if self.current is None:return
        d=self.decks[self.active]; item=self.current_item()
        self.apply_audio()
        if d.kind=='pdf':
            if self.pdf_auto.isChecked() and not d.pdf_source.loading:
                self.elapsed+=dt
                if self.elapsed>=item['seconds']:self.elapsed=0;self.advance()
            return
        if d.kind=='image':
            self.elapsed+=dt; fraction=self.elapsed/item['seconds']
            if fraction>=1:self.advance()
        else:
            if d.player.mediaStatus()==QMediaPlayer.EndOfMedia:
                self.advance();return
            start,end=clip_bounds(d.config,d.player.duration());duration=end-start;position=d.player.position()
            fraction=(position-start)/duration if duration else 0
            if end and position>=end:self.advance();return
            # Start overlap only near the end; short videos use their end-of-media event.
            remaining=end-position
            if duration>self.duration.value()*2000 and 0<remaining<=self.duration.value()*1000 and self.effect.currentText()!='直接切換':
                if self.cue_item is not None:
                    if self.mode.currentText()!='播放一次':self.advance()
                elif following(self.lists,self.current,self.mode.currentText()) is not None:self.advance()
        if not self.seek.isSliderDown():self.seek.setValue(int(min(1,fraction)*1000))
    def seek_to(self):
        if self.current is None or self.pending or self.transition:return
        d=self.decks[self.active]
        if d.kind=='pdf':d.pdf_source.set_page(round((d.pdf_source.count-1)*self.seek.value()/1000))
        elif d.kind=='video':
            start,end=clip_bounds(d.config,d.player.duration());d.player.setPosition(start+int((end-start)*self.seek.value()/1000))
        else:self.elapsed=self.current_item()['seconds']*self.seek.value()/1000
    def refresh_media_fit(self,*_):
        for d in self.decks:d.relayout(self.fit.currentIndex())
        if hasattr(self,'single_editor'):self.single_editor.sync()
    def refresh_output_fit(self,*_):
        if hasattr(self,'output_view'):
            self.output_view.fit_mode=[1,0,2][self.output_fit.currentIndex()];self.output_view.refit()
    def fill_output(self):
        if self.presentations.active:
            screen=self.output_view.screen();self.presentations.move_output(screen,QApplication.screens().index(screen));return
        if self.compositor.enabled:self.compositor.full_bleed()
        else:
            if self.current is not None:self.single_editor.apply(0,0,1)
            self.fit.setCurrentIndex(2);self.refresh_media_fit();self.persist_session()
        self.output_fit.setCurrentIndex(1);self.refresh_output_fit()
    def output(self):
        if self.presentations.active:self.presentations.command('focus');return
        if self.output_view.isFullScreen():self.output_view.showNormal()
        else:self.output_view.showFullScreen()
        QTimer.singleShot(0,self.output_view.refit)
    def choose_output(self):
        screens=QApplication.screens();labels=[f'{i+1}. {s.name()} / {round(s.size().width()*s.devicePixelRatio())}×{round(s.size().height()*s.devicePixelRatio())} 像素（縮放 {s.devicePixelRatio():g}×）' for i,s in enumerate(screens)]
        label,ok=QInputDialog.getItem(self,'選擇輸出螢幕','螢幕',labels,0,False)
        if ok:
            screen=screens[labels.index(label)]
            if self.presentations.active:self.presentations.move_output(screen,labels.index(label));return
            self.output_view.showNormal();self.output_view.winId();self.output_view.windowHandle().setScreen(screen);self.output_view.setGeometry(screen.geometry());self.output()
    def settings(self):return {'canvas_width':int(self.screen.sceneRect().width()),'canvas_height':int(self.screen.sceneRect().height()),'ppt_timings':hasattr(self,'presentations') and self.presentations.timings.isChecked(),'pdf_auto':self.pdf_auto.isChecked(),'end_action':self.end_action.currentData(),'hold_last':self.hold_last.isChecked(),'performance':self.compositor.performance.isChecked(),'mode':self.mode.currentText(),'effect':self.effect.currentText(),'duration':self.duration.value(),'volume':self.volume.value(),'fit':self.fit.currentIndex(),'output_fit':self.output_fit.currentIndex(),'multi':getattr(self,'compositor',None) is not None and self.compositor.enabled}
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
    def configure_canvas(self):
        presets=['1920×1080 Full HD','3840×2160 4K UHD','4096×2160 DCI 4K','1080×1920 直式','2160×3840 直式 4K','自訂像素']
        choice,ok=QInputDialog.getItem(self,'畫布像素','選擇尺寸',presets,0,False)
        if not ok:return
        if choice=='自訂像素':
            width,ok=QInputDialog.getInt(self,'自訂畫布','寬度（像素）',int(self.screen.sceneRect().width()),80,4096)
            if not ok:return
            height,ok=QInputDialog.getInt(self,'自訂畫布','高度（像素）',int(self.screen.sceneRect().height()),45,4096)
            if not ok:return
        else:width,height=map(int,choice.split()[0].split('×'))
        self.set_canvas(width,height);self.output_fit.setCurrentIndex(1);self.persist_session()
        self.status.setText(f'畫布 {width}×{height} 像素；全螢幕輸出依目標螢幕實際解析度。')
    def set_canvas(self,width,height):
        width=max(80,min(4096,int(width)));height=max(45,min(4096,int(height)))
        old=self.screen.sceneRect();sx,sy=width/old.width(),height/old.height()
        self.screen.scene().setSceneRect(0,0,width,height);self.screen.canvas_root.setRect(0,0,width,height)
        for view in (self.screen,self.output_view,self.preview_view):view.setSceneRect(0,0,width,height);view.refit()
        for layer in self.compositor.layers:
            x,y=layer.pos().x()*sx,layer.pos().y()*sy;layer.resize_to(layer.c['w']*sx,layer.c['h']*sy);layer.setPos(x,y)
        for key,high in [('x',width),('y',height),('w',width),('h',height)]:
            self.compositor.controls[key].blockSignals(True);self.compositor.controls[key].setMaximum(high);self.compositor.controls[key].blockSignals(False)
        self.refresh_media_fit();self.compositor.sync_controls()
    def apply_settings(self,s):
        self.pdf_auto.setChecked(s.get('pdf_auto',False))
        if hasattr(self,'presentations'):self.presentations.timings.setChecked(s.get('ppt_timings',False))
        self.set_canvas(s.get('canvas_width',1920),s.get('canvas_height',1080));self.hold_last.setChecked(s.get('end_action','hold' if s.get('hold_last',True) else 'hide')!='hide');self.compositor.performance.setChecked(s.get('performance',True))
        self.mode.setCurrentText(s.get('mode',MODES[0]));self.effect.setCurrentText(s.get('effect',EFFECTS[0]));self.duration.setValue(float(s.get('duration',1)));self.volume.setValue(int(s.get('volume',80)));self.fit.setCurrentIndex(int(s.get('fit',0)));self.output_fit.setCurrentIndex(int(s.get('output_fit',0)))
    def formats(self):
        fmt=QMediaFormat();formats=fmt.supportedFileFormats(QMediaFormat.Decode);codecs=fmt.supportedVideoCodecs(QMediaFormat.Decode)
        QMessageBox.information(self,'這台電腦的解碼能力','封裝格式：\n'+', '.join(QMediaFormat.fileFormatName(f) for f in formats)+'\n\n影片編碼：\n'+', '.join(QMediaFormat.videoCodecName(c) for c in codecs)+'\n\n副檔名不代表編碼。受 DRM 保護、損壞或未支援的編碼無法保證播放。')
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls():e.acceptProposedAction()
    def dropEvent(self,e):self.add_files([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])
    def closeEvent(self,e):
        if hasattr(self,'presentations') and not self.presentations.shutdown():
            self.status.setText('PowerPoint 正在結束放映，請稍候再關閉。');e.ignore();return
        for editor in list(getattr(self,'video_editors',{}).values()):editor.close()
        self.persist_session();self.screen.scene().selectionChanged.disconnect(self.compositor.scene_selection);self.stop();self.screen.exit_callback=None;self.screen.close();self.output_view.close();self.preview_view.close();super().closeEvent(e)

if __name__=='__main__':
    app=QApplication(sys.argv);app.setApplicationName('Media Carousel');window=Window();window.show()
    if '--build-smoke-test' in sys.argv:
        import json
        report=Path(sys.argv[sys.argv.index('--build-smoke-test')+1])
        from smoke_media import write_fixture
        fixture=report.with_suffix('.mp4');write_fixture(fixture)
        window.session_ready=False
        if hasattr(window,'session_timer'):window.session_timer.stop()
        window.stop();window.compositor.enable.setChecked(False)
        for deck in window.decks:deck.player.setAudioOutput(None)
        window.lists=[{'name':'Native check','items':[{'path':str(fixture),'seconds':30,'start':1,'end':4} for _ in range(2)]}]
        window.refresh_groups();window.mode.setCurrentText('清單循環');window.effect.setCurrentText('直接切換');window.request((0,0));smoke_started=time.monotonic()
        def finish_smoke():
            job=window.next_cache.jobs.get(window)
            standby=window.decks[job['index']] if job else None
            ready=bool(standby and standby.preroll.ready)
            if not ready and time.monotonic()-smoke_started<12:QTimer.singleShot(100,finish_smoke);return
            preroll_ok=False;finish_ok=False
            if ready:
                changes=[];standby.player.sourceChanged.connect(lambda url:changes.append(url))
                frame=standby.last_frame
                preroll_ok=standby.audio.volume()==0 and standby.player.playbackState()==QMediaPlayer.PausedState and frame is not None and frame.width()==160 and frame.height()==90 and frame.startTime()>=1000000 and standby.player.hasAudio()
                window.advance_media();preroll_ok=preroll_ok and window.decks[window.active] is standby and not window.pending and not window.transition and not changes
                window.end_action.setCurrentIndex(0);window.request(None)
                finish_ok=window.held and not window.running and standby.image.isVisible() and not standby.image.pixmap().isNull()
                window.end_action.setCurrentIndex(1);window.request(None)
                finish_ok=finish_ok and window.current is None and all(not d.video.isVisible() and not d.image.isVisible() for d in window.decks)
            codecs=QMediaFormat().supportedVideoCodecs(QMediaFormat.Decode)
            from PySide6.QtGui import QPdfWriter,QColor
            from PySide6.QtCore import QSize
            from PySide6.QtPdf import QPdfDocument
            pdfpath=report.with_suffix('.pdf');writer=QPdfWriter(str(pdfpath));painter=QPainter(writer);painter.fillRect(0,0,writer.width(),writer.height(),QColor('green'));painter.end();del writer
            pdf=QPdfDocument();error=pdf.load(str(pdfpath));pdf_ok=error==QPdfDocument.Error.None_ and not pdf.render(0,QSize(80,80)).isNull();pdf.close()
            bridge_ok=True
            mac_bridge_ok=True
            if sys.platform=='win32':
                try:import pythoncom,win32com.client
                except Exception:bridge_ok=False
            elif sys.platform=='darwin':
                from powerpoint_mac import verify_mac_bridge
                mac_bridge_ok=verify_mac_bridge()
            from audio_meter import levels
            from PySide6.QtMultimedia import QAudioBuffer,QAudioFormat
            from PySide6.QtCore import QByteArray
            import struct
            fmt=QAudioFormat();fmt.setSampleRate(48000);fmt.setChannelCount(2);fmt.setSampleFormat(QAudioFormat.Int16)
            pcm_ok=levels(QAudioBuffer(QByteArray(struct.pack('<hhhh',16384,-8192,-16384,8192)),fmt))[0]==[.5,.25]
            ok=window.isVisible() and bool(QApplication.screens()) and bool(codecs) and pdf_ok and bridge_ok and pcm_ok and preroll_ok and finish_ok and mac_bridge_ok
            report.write_text(json.dumps({'ok':ok,'video_codecs':len(codecs),'pdf':pdf_ok,'powerpoint_bridge':bridge_ok,'mac_ppt_bridge':mac_bridge_ok,'mac_office_live_tested':False,'pcm_meter':pcm_ok,'video_preroll':preroll_ok,'finish_policy':finish_ok}),encoding='utf-8')
            window.close();app.exit(0 if ok else 1)
        QTimer.singleShot(1500,finish_smoke)
    sys.exit(app.exec())

