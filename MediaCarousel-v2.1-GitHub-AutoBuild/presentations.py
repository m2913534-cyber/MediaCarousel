"""Presentation routing, native PowerPoint lifecycle and presenter keyboard input."""
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import QObject,QEvent,QTimer,Qt
from PySide6.QtWidgets import (QApplication,QWidget,QHBoxLayout,QLabel,QPushButton,QSpinBox,
    QCheckBox,QLineEdit,QAbstractSpinBox,QComboBox,QTextEdit,QPlainTextEdit,QGraphicsRectItem)
from PySide6.QtGui import QPen,QAction
from model import is_pdf,is_powerpoint,media_name
from powerpoint import PowerPointWorker,powerpoint_available

class PresentationController(QObject):
    def __init__(self,host):
        super().__init__(host);self.host=host;self.active=False;self.starting=False;self.generation=0;self.payload=None;self.native_state={};self.black=False
        self.worker=PowerPointWorker();self.worker.opened.connect(self.native_opened);self.worker.progress.connect(self.native_progress);self.worker.ended.connect(self.native_ended);self.worker.failed.connect(self.native_failed)
        self.notice=QLabel(host.screen.viewport());self.notice.setAlignment(Qt.AlignCenter);self.notice.setWordWrap(True);self.notice.setAttribute(Qt.WA_TransparentForMouseEvents);self.notice.setObjectName('PowerPointNotice');self.notice.hide()
        self.overlay=QGraphicsRectItem(host.screen.canvas_root);self.overlay.setPen(QPen(Qt.NoPen));self.overlay.setBrush(Qt.black);self.overlay.setZValue(10000000);self.overlay.hide()
        self.controls=QWidget();self.controls.setProperty('panel',True);r=QHBoxLayout(self.controls);r.setContentsMargins(5,4,5,4);r.setSpacing(6)
        self.label=QLabel('簡報');r.addWidget(self.label)
        def add(text,fn):
            b=QPushButton(text);b.clicked.connect(lambda checked=False:fn());r.addWidget(b);return b
        add('← 上一頁',lambda:self.step(True));add('下一步 →',lambda:self.step(False))
        self.page=QSpinBox();self.page.setRange(1,1);self.page.setPrefix('頁 ');self.page.setKeyboardTracking(False);self.page.valueChanged.connect(self.goto);r.addWidget(self.page)
        add('黑畫面 B',self.toggle_black);add('結束 Esc',self.exit)
        self.pen=QCheckBox('簡報筆');self.pen.setChecked(host.interface.preferences.value('presenter',True,type=bool));self.pen.setToolTip('支援常見 USB／藍牙鍵盤模式簡報筆：Page Up／Down、方向鍵、空白鍵、B、Esc。輸入欄位不攔截按鍵。')
        self.pen.toggled.connect(lambda value:host.interface.preferences.setValue('presenter',value));r.addWidget(self.pen);r.addStretch()
        host.interface.viewer_layout.insertWidget(2,self.controls);self.controls.hide()
        menu=host.menuBar().addMenu('簡報');a=QAction('偵測 PowerPoint 桌面版',host);a.triggered.connect(self.detect);menu.addAction(a)
        toggle=QAction('啟用簡報筆按鍵',host);toggle.setCheckable(True);toggle.setChecked(self.pen.isChecked());toggle.toggled.connect(self.pen.setChecked);self.pen.toggled.connect(toggle.setChecked);menu.addAction(toggle)
        a=QAction('從列表播放所選簡報',host);a.triggered.connect(host.play_selected);menu.addAction(a)
        self.timings=QAction('PPT 使用原有自動換頁時間',host);self.timings.setCheckable(True);menu.addAction(self.timings)
        for text,fn in [('上一頁／步驟',lambda:self.step(True)),('下一頁／步驟',lambda:self.step(False)),('第一頁',lambda:self.command('first')),('最後一頁',lambda:self.command('last')),('黑畫面',self.toggle_black),('結束簡報',self.exit)]:
            a=QAction(text,host);a.triggered.connect(fn);menu.addAction(a)
        QApplication.instance().installEventFilter(self)
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(125)
    def pdf_deck(self):
        h=self.host
        if h.pending or h.transition:return None
        if h.compositor.enabled:
            layer=h.compositor.selected()
            if layer and not layer.pending and not layer.transition:
                deck=layer.decks[layer.active]
                if deck.kind=='pdf' and layer.current is not None:return deck
        elif h.current is not None:
            d=h.decks[h.active]
            if d.kind=='pdf':return d
        return None
    def refresh(self):
        deck=self.pdf_deck();self.controls.setVisible(self.active or deck is not None or self.starting)
        if self.active:
            state=self.native_state;self.label.setText('PPT · 原生音效');page,count=state.get('slide',1),state.get('total',1)
            self.notice.setGeometry(self.host.screen.viewport().rect());self.notice.setText(f"PowerPoint 原生輸出\n{media_name(self.host.current_item())}\n投影片 {page} / {count} · 動畫步驟 {state.get('click',0)}\n音效由 PowerPoint／系統音量控制")
        elif deck:
            self.label.setText('PDF');page,count=deck.pdf_source.page+1,deck.pdf_source.count
            if not self.host.seek.isSliderDown():self.host.seek.setValue(round((page-1)/max(1,count-1)*1000))
        else:
            page,count=1,1;self.label.setText('正在啟動 PowerPoint…' if self.starting else '簡報')
            if self.black:self.black=False;self.overlay.hide()
        self.page.blockSignals(True);self.page.setRange(1,max(1,count));self.page.setValue(page);self.page.blockSignals(False)
        self.overlay.setRect(self.host.screen.canvas_root.rect())
    def detect(self):
        ok,message=powerpoint_available();self.host.status.setText(message);return ok
    def start_native(self,target,item,override=False):
        h=self.host
        if h.compositor.enabled:h.status.setText('PowerPoint 動畫簡報使用獨立原生輸出，請切回單畫面。');return
        if not Path(item['path']).is_file():h.status.setText('PowerPoint 檔案遺失：'+media_name(item));return
        ok,message=powerpoint_available()
        if not ok:h.status.setText(message);return
        self.generation+=1;self.starting=True;self.payload=(target,deepcopy(item),override)
        screen=h.output_view.screen() or QApplication.primaryScreen();screens=QApplication.screens();index=screens.index(screen) if screen in screens else 0
        args={'path':item['path'],'screen_name':screen.name(),'index':index,'slide':item.get('ppt_slide',1),'click':item.get('ppt_click',0),'timings':self.timings.isChecked(),'_token':self.generation}
        self.worker.submit('start',args);h.status.setText('正在以 PowerPoint 啟動原生動畫與音效…')
    def native_opened(self,state):
        if state.get('_token')!=self.generation or not self.starting:return
        h=self.host;target,item,override=self.payload
        p,i=target
        # The user may change lists while Office is opening. Keep this playback snapshot valid.
        override=override or not (0<=p<len(h.lists) and 0<=i<len(h.lists[p]['items']) and h.lists[p]['items'][i].get('path')==item['path'])
        h.stop_single();self.starting=False;self.active=True;h.current=target;h.cue_item=deepcopy(item) if override else None
        if not override:h.groups.setCurrentIndex(target[0]);h.files.setCurrentRow(target[1])
        h.running=True;h.output_view.hide();self.notice.show();self.native_progress(state);h.status.setText('PowerPoint 原生放映已啟動；可用簡報筆或簡報控制列操作。')
    def native_progress(self,state):
        if state.get('_token')!=self.generation or not self.active:return
        self.native_state=state
        if self.host.current is not None:self.host.current_item().update(ppt_slide=state['slide'],ppt_click=state.get('click',0))
        self.refresh()
    def native_ended(self,token):
        if token!=self.generation:return
        was_active=self.active;self.active=False;self.starting=False;self.notice.hide()
        if was_active:self.host.stop_single();self.host.status.setText('PowerPoint 放映已結束。')
    def native_failed(self,token,message):
        if token!=self.generation:return
        was_active=self.active;self.starting=False;self.active=False;self.notice.hide()
        if was_active:self.host.stop_single()
        self.host.status.setText(message)
    def stop(self):
        running=self.active or self.starting;self.generation+=1;self.active=False;self.starting=False;self.notice.hide();self.black=False;self.overlay.hide()
        if running:self.worker.submit('stop')
    def step(self,reverse=False):
        if self.active:self.worker.submit('previous' if reverse else 'next');return True
        deck=self.pdf_deck()
        if deck is not None:
            result=deck.pdf_source.step(reverse)
            if not result:self.host.status.setText('已到第一頁。' if reverse else '已到最後一頁。')
            return True
        return False
    def goto(self,page):
        if self.active:self.worker.submit('goto',page)
        else:
            deck=self.pdf_deck()
            if deck:deck.pdf_source.set_page(page-1)
    def command(self,name):
        if self.active:self.worker.submit(name);return
        deck=self.pdf_deck()
        if deck:
            if name=='first':deck.pdf_source.set_page(0)
            elif name=='last':deck.pdf_source.set_page(deck.pdf_source.count-1)
    def toggle_black(self):
        if self.active:self.worker.submit('black');return
        if self.pdf_deck() is not None:self.black=not self.black;self.overlay.setRect(self.host.screen.canvas_root.rect());self.overlay.setVisible(self.black)
    def move_output(self,screen,index):
        self.host.output_view.winId();self.host.output_view.windowHandle().setScreen(screen)
        if self.active:self.worker.submit('move',{'screen_name':screen.name(),'index':index})
    def exit(self):
        if self.active or self.starting or self.pdf_deck() is not None:self.host.stop();self.host.output_view.showNormal()
    def shutdown(self):
        self.stop();return self.worker.shutdown()
    def input_context(self):
        app=QApplication.instance();h=self.host
        if app.activeModalWidget() is not None:return False
        if app.activeWindow() not in (h,h.output_view,h.preview_view):return False
        focus=app.focusWidget()
        return not isinstance(focus,(QLineEdit,QAbstractSpinBox,QComboBox,QTextEdit,QPlainTextEdit))
    def eventFilter(self,obj,event):
        if event.type() not in (QEvent.ShortcutOverride,QEvent.KeyPress,QEvent.KeyRelease) or not self.pen.isChecked():return False
        if not self.input_context():return False
        key=event.key();active=self.active or self.pdf_deck() is not None
        selected=self.host.files.currentRow();items=self.host.lists[self.host.group_index()]['items']
        selected_document=0<=selected<len(items) and (is_pdf(items[selected]) or is_powerpoint(items[selected]))
        if key==Qt.Key_F5 and selected_document and not event.modifiers() & (Qt.ControlModifier|Qt.AltModifier|Qt.MetaModifier):
            if event.type()==QEvent.KeyPress and not event.isAutoRepeat():self.host.play_selected()
            event.accept();return True
        if not active or event.modifiers() & (Qt.ControlModifier|Qt.AltModifier|Qt.MetaModifier):return False
        next_keys=(Qt.Key_PageDown,Qt.Key_Right,Qt.Key_Down,Qt.Key_Space,Qt.Key_N,Qt.Key_Return,Qt.Key_Enter)
        prev_keys=(Qt.Key_PageUp,Qt.Key_Left,Qt.Key_Up,Qt.Key_P,Qt.Key_Backspace)
        commands={Qt.Key_Home:'first',Qt.Key_End:'last',Qt.Key_B:'black',Qt.Key_Escape:'exit'}
        if key not in next_keys+prev_keys and key not in commands:return False
        if event.type()==QEvent.KeyPress and not event.isAutoRepeat():
            if key in next_keys:self.step(False)
            elif key in prev_keys:self.step(True)
            elif commands[key]=='black':self.toggle_black()
            elif commands[key]=='exit':self.exit()
            else:self.command(commands[key])
        event.accept();return True
