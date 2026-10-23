"""Interchangeable desktop layouts and palettes; playback objects stay in place."""
from pathlib import Path
from PySide6.QtCore import Qt,QSettings,QTimer,QSize
from PySide6.QtGui import QAction,QActionGroup,QFont
from PySide6.QtWidgets import (QApplication,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,
    QPushButton,QLabel,QComboBox,QDoubleSpinBox,QSlider,QListWidget,QListView,QDockWidget,
    QToolBar,QToolButton,QMenu,QScrollArea,QSizePolicy,QAbstractItemView,QWidgetAction)
from model import MODES,EFFECTS,media_name

NAMES=['導播控台','明亮工作室','舞台演出','精簡工作台']
PALETTES=[
 {'bg':'#121820','panel':'#1b2531','raised':'#293647','text':'#e9f0f7','dim':'#a6b7c9','line':'#344458','accent':'#65dfc6','ink':'#082b25'},
 {'bg':'#edf1eb','panel':'#fcfdf8','raised':'#e5ece2','text':'#273e34','dim':'#5e7367','line':'#c8d7ca','accent':'#39745d','ink':'#ffffff'},
 {'bg':'#10100f','panel':'#1c1b18','raised':'#302d25','text':'#f6f0e1','dim':'#c3baa7','line':'#484230','accent':'#edc26c','ink':'#271f10'},
 {'bg':'#eff2f8','panel':'#ffffff','raised':'#e8ecf5','text':'#29364b','dim':'#63748e','line':'#d0d8e8','accent':'#6666bc','ink':'#ffffff'},
]

def button(layout,text,fn,name=None):
    b=QPushButton(text)
    if name:b.setObjectName(name)
    b.clicked.connect(lambda checked=False:fn());layout.addWidget(b);return b

def row(parent):
    r=QHBoxLayout();r.setSpacing(6);parent.addLayout(r);return r

def panel():
    w=QWidget();w.setProperty('panel',True);v=QVBoxLayout(w);v.setContentsMargins(12,12,12,12);v.setSpacing(9);return w,v

def action(menu,text,fn,shortcut=None):
    a=QAction(text,menu)
    if shortcut:a.setShortcut(shortcut)
    a.triggered.connect(lambda checked=False:fn());menu.addAction(a);return a

class CuePanel(QWidget):
    def __init__(self,compositor):
        super().__init__();self.c=compositor;self.setProperty('panel',True)
        v=QVBoxLayout(self);v.setContentsMargins(12,10,12,10);v.setSpacing(7)
        r=row(v);self.heading=QLabel('CUE · 演出流程');self.heading.setObjectName('PanelHeading');r.addWidget(self.heading);r.addStretch()
        button(r,'＋ 記錄',compositor.remember)
        more=QToolButton();more.setText('管理 ▾');menu=QMenu(more)
        for name,fn in [('覆寫所選 CUE',compositor.overwrite),('重新命名',compositor.rename_scene),('刪除所選 CUE',compositor.delete_scene)]:action(menu,name,fn)
        more.setMenu(menu);more.setPopupMode(QToolButton.InstantPopup);r.addWidget(more)
        self.view=QListView();self.view.setObjectName('CueList');self.view.setModel(compositor.scene_list.model());self.view.setEditTriggers(QAbstractItemView.NoEditTriggers);self.view.setMinimumHeight(65)
        self.view.selectionModel().currentChanged.connect(lambda index,previous:compositor.scene_list.setCurrentIndex(index.row()))
        self.view.doubleClicked.connect(lambda index:compositor.recall());compositor.scene_list.currentIndexChanged.connect(self.sync_selection);v.addWidget(self.view,1)
        r=row(v);r.addStretch();self.go=button(r,'GO · 召回',compositor.recall,'PrimaryButton');self.next=button(r,'下一個 GO →',compositor.next_cue,'NextCueButton')
        self.go.setMinimumWidth(130);self.next.setMinimumWidth(150)
        self.caption=QLabel('記憶來源、播放位置與調整參數');self.caption.setObjectName('SecondaryLabel');self.caption.setWordWrap(True);v.addWidget(self.caption)
    def sync_selection(self,i):
        if i>=0:self.view.setCurrentIndex(self.c.scene_list.model().index(i,0))
    def set_performance(self,on):
        self.view.setViewMode(QListView.IconMode if on else QListView.ListMode)
        self.view.setFlow(QListView.LeftToRight if on else QListView.TopToBottom);self.view.setWrapping(False);self.view.setResizeMode(QListView.Adjust)
        self.view.setGridSize(QSize(190,56) if on else QSize());self.view.setSpacing(5 if on else 0)
        self.caption.setVisible(not on);self.go.setMinimumHeight(42 if on else 30);self.next.setMinimumHeight(42 if on else 30)

class Interface:
    def __init__(self,host):
        self.host=host;self.preferences=QSettings('MediaCarousel','Interface');self.theme_index=0;self.layout_index=0;self.docks=[]
        QApplication.setStyle('Fusion');host.setDockNestingEnabled(True);host.setTabPosition(Qt.AllDockWidgetAreas,__import__('PySide6.QtWidgets',fromlist=['QTabWidget']).QTabWidget.North)
        self.build_assets();self.build_viewer();self.build_playback();self.build_chrome()
    def dock(self,name,title,widget,area):
        d=QDockWidget(title,self.host);d.setObjectName(name);d.setWidget(widget);d.setAllowedAreas(Qt.AllDockWidgetAreas);d.setMinimumSize(180,100)
        self.host.addDockWidget(area,d);self.docks.append(d);return d
    def build_assets(self):
        h=self.host;w,v=panel();w.setObjectName('LibraryPanel')
        r=row(v);h.groups=QComboBox();h.groups.currentIndexChanged.connect(h.render);r.addWidget(h.groups,1)
        more=QToolButton();more.setText('清單 ▾');menu=QMenu(more)
        for name,fn in [('新增清單',h.new_list),('重新命名',h.rename_list),('刪除清單',h.delete_list)]:action(menu,name,fn)
        more.setMenu(menu);more.setPopupMode(QToolButton.InstantPopup);r.addWidget(more)
        h.files=QListWidget();h.files.setObjectName('MediaList');h.files.setContextMenuPolicy(Qt.CustomContextMenu);h.files.customContextMenuRequested.connect(h.media_menu);h.files.itemDoubleClicked.connect(lambda _:h.play_selected());h.files.currentRowChanged.connect(h.selection);v.addWidget(h.files,1)
        r=row(v);button(r,'＋ 媒體',h.add_files,'PrimaryButton');button(r,'＋ 黑畫面',h.add_black);button(r,'移除',h.remove)
        r=row(v);button(r,'↑',lambda:h.move(-1));button(r,'↓',lambda:h.move(1));button(r,'套用到所選格子',lambda:h.compositor.use_selected_file())
        self.asset_detail_toggle=QToolButton();self.asset_detail_toggle.setText('▸ 素材參數');self.asset_detail_toggle.setCheckable(True);self.asset_detail_toggle.setToolButtonStyle(Qt.ToolButtonTextOnly);v.addWidget(self.asset_detail_toggle)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setMaximumHeight(310);scroll.setVisible(False);details,dv=panel();scroll.setWidget(details);v.addWidget(scroll)
        self.asset_detail_toggle.toggled.connect(scroll.setVisible)
        form=QFormLayout();dv.addLayout(form);h.seconds=QDoubleSpinBox();h.seconds.setRange(.5,86400);h.seconds.setValue(5);h.seconds.setSuffix(' 秒');h.seconds.valueChanged.connect(h.set_seconds);form.addRow('圖片／PDF／黑場',h.seconds)
        h.clip_start=QDoubleSpinBox();h.clip_end=QDoubleSpinBox()
        for label,spin in [('開始秒',h.clip_start),('結束秒 · 0＝片尾',h.clip_end)]:spin.setRange(0,86400);spin.setDecimals(2);form.addRow(label,spin)
        h.clip_gain=QDoubleSpinBox();h.clip_gain.setRange(0,100);h.clip_gain.setValue(100);h.clip_gain.setSuffix(' %');form.addRow('素材音量',h.clip_gain)
        from PySide6.QtWidgets import QCheckBox
        h.clip_mute=QCheckBox('素材靜音');dv.addWidget(h.clip_mute);button(dv,'套用片段與音量',h.edit_clip);button(dv,'套用圖片／PDF 秒數到本清單',h.apply_seconds)
        tip=QLabel('影片可按右鍵開啟獨立編輯視窗。');tip.setWordWrap(True);tip.setObjectName('SecondaryLabel');dv.addWidget(tip)
        self.asset_dock=self.dock('AssetDock','素材庫',w,Qt.LeftDockWidgetArea)
    def build_viewer(self):
        h=self.host;root=QWidget();root.setObjectName('ProgramPanel');h.setCentralWidget(root);v=QVBoxLayout(root);v.setContentsMargins(14,12,14,8);v.setSpacing(9)
        r=row(v);self.program_label=QLabel('PROGRAM · 輸出預覽');self.program_label.setObjectName('PanelHeading');r.addWidget(self.program_label);r.addStretch();self.canvas_label=QLabel('1920 × 1080');self.canvas_label.setObjectName('SecondaryLabel');r.addWidget(self.canvas_label)
        self.viewer_layout=v;v.addWidget(h.screen,1);h.screen.setMinimumSize(180,100)
        r=row(v);self.source_label=QLabel('尚未播放');self.source_label.setObjectName('SecondaryLabel');r.addWidget(self.source_label,1);self.time_label=QLabel('00:00 / 00:00');self.time_label.setObjectName('TimeLabel');r.addWidget(self.time_label)
        h.seek=QSlider(Qt.Horizontal);h.seek.setRange(0,1000);h.seek.sliderReleased.connect(h.seek_to);v.addWidget(h.seek)
        r=row(v);button(r,'⏮',lambda:h.advance(True));h.play_btn=button(r,'▶ 播放／暫停',h.toggle,'PrimaryButton');button(r,'■ 停止',h.stop,'StopButton');button(r,'⏭',h.advance);r.addStretch()
        self.edit_button=button(r,'拖曳縮放',h.free_transform);button(r,'一鍵滿版',h.fill_output)
        self.edit_button.setToolTip('開啟八個控制點：左右只調寬度、上下只調高度，四角可自由拉伸。拖曳中央移動；Shift＋滾輪調寬，Alt＋滾輪調高。')
        r=row(v);r.addWidget(QLabel('主音量'));h.volume=QSlider(Qt.Horizontal);h.volume.setRange(0,100);h.volume.setValue(80);h.volume.setMaximumWidth(180);r.addWidget(h.volume)
        self.volume_label=QLabel('80%');h.volume.valueChanged.connect(lambda n:self.volume_label.setText(str(n)+'%'));r.addWidget(self.volume_label)
        self.playback_button=QToolButton();self.playback_button.setObjectName('PlaybackOutputButton');self.playback_button.setText('播放及輸出 ▾');self.playback_button.setMinimumWidth(128);self.playback_button.setAccessibleName('播放及輸出參數');self.playback_button.setToolTip('調整輪播、轉場、滿版比例、畫布與輸出螢幕。');r.addWidget(self.playback_button);r.addStretch()
        h.status=QLabel('加入媒體後即可播放。Space 播放／暫停 · F11 全螢幕');h.status.setWordWrap(True);h.status.setObjectName('SecondaryLabel');v.addWidget(h.status)
        self.info_timer=QTimer(h);self.info_timer.timeout.connect(self.refresh_info);self.info_timer.start(250)
    def build_playback(self):
        h=self.host;self.playback_menu=QMenu(self.playback_button);self.playback_menu.setObjectName('PlaybackOutputMenu')
        self.playback_scroll=QScrollArea();self.playback_scroll.setWidgetResizable(True);self.playback_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.playback_widget,v=panel();self.playback_widget.setObjectName('PlaybackOutputPanel');self.playback_scroll.setWidget(self.playback_widget)
        heading=row(v);label=QLabel('播放及輸出');label.setObjectName('PanelHeading');heading.addWidget(label);heading.addStretch();button(heading,'收起',self.playback_menu.hide)
        form=QFormLayout();form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow);form.setRowWrapPolicy(QFormLayout.WrapLongRows);v.addLayout(form)
        h.mode=QComboBox();h.mode.addItems(MODES);form.addRow('輪播模式',h.mode)
        h.effect=QComboBox();h.effect.addItems(EFFECTS);form.addRow('切換效果',h.effect)
        h.duration=QDoubleSpinBox();h.duration.setRange(.1,10);h.duration.setValue(1);h.duration.setSuffix(' 秒');form.addRow('轉場時間',h.duration)
        from PySide6.QtWidgets import QCheckBox
        h.pdf_auto=QCheckBox('PDF 每頁自動輪播（依素材秒數）');v.addWidget(h.pdf_auto)
        h.hold_last=QCheckBox('播放一次結束時停留最後一幀');h.hold_last.setChecked(True);v.addWidget(h.hold_last)
        h.fit=QComboBox();h.fit.addItems(['完整顯示（保留黑邊）','填滿畫面（裁切）','強制滿版（拉伸至畫布）']);h.fit.currentIndexChanged.connect(h.refresh_media_fit);form.addRow('單畫面填滿',h.fit)
        h.output_fit=QComboBox();h.output_fit.addItems(['滿螢幕（等比例裁切）','完整畫布（保留黑邊）','延展至螢幕（可能變形）']);h.output_fit.currentIndexChanged.connect(h.refresh_output_fit);form.addRow('投影比例',h.output_fit)
        def launch(fn):self.playback_menu.hide();fn()
        for text,fn in [('畫布像素／4K',h.configure_canvas),('選擇輸出螢幕',h.choose_output),('開啟預覽視窗',h.show_preview)]:button(v,text,lambda fn=fn:launch(fn))
        v.addStretch()
        self.playback_action=QWidgetAction(self.playback_menu);self.playback_action.setDefaultWidget(self.playback_scroll);self.playback_menu.addAction(self.playback_action)
        self.playback_button.setMenu(self.playback_menu);self.playback_button.setPopupMode(QToolButton.InstantPopup);self.playback_menu.aboutToShow.connect(self.size_playback_menu)
    def size_playback_menu(self):
        # Anchor beside master volume without changing the preview's geometry.
        screen=QApplication.screenAt(self.playback_button.mapToGlobal(self.playback_button.rect().center())) or self.playback_button.screen()
        self.playback_widget.ensurePolished();available=screen.availableGeometry();width=min(450,max(240,available.width()-32));height=min(560,max(180,available.height()-80),self.playback_widget.sizeHint().height())
        self.playback_scroll.setFixedSize(width,height)
    def build_chrome(self):
        h=self.host;project=h.menuBar().addMenu('專案')
        action(project,'開啟專案…',h.open_project,'Ctrl+O');action(project,'儲存專案…',h.save,'Ctrl+S');project.addSeparator();action(project,'格式與解碼資訊',h.formats)
        self.view_menu=h.menuBar().addMenu('檢視');appearance=h.menuBar().addMenu('介面外觀');self.theme_actions=[];self.layout_actions=[]
        for label,fn,store in [('整體風格',self.apply_theme,self.theme_actions),('版型配置',self.apply_layout,self.layout_actions)]:
            menu=appearance.addMenu(label);group=QActionGroup(h);group.setExclusive(True)
            for i,name in enumerate(NAMES):
                a=QAction(name,h);a.setCheckable(True);group.addAction(a);menu.addAction(a);store.append(a);a.triggered.connect(lambda checked=False,n=i,f=fn:f(n))
        action(appearance,'恢復導播控台預設',lambda:self.reset())
        bar=QToolBar('主工具列',h);bar.setObjectName('MainToolbar');bar.setMovable(False);h.addToolBar(Qt.TopToolBarArea,bar)
        brand=QLabel('  MEDIA CAROUSEL  ');brand.setObjectName('BrandLabel');bar.addWidget(brand)
        action(bar,'素材',lambda:self.toggle_dock(self.asset_dock));action(bar,'CUE',lambda:self.toggle_dock(self.cue_dock));action(bar,'參數',lambda:self.toggle_dock(h.compositor))
        bar.addSeparator();action(bar,'畫布／4K',h.configure_canvas);action(bar,'輸出螢幕',h.choose_output);out=action(bar,'全螢幕輸出',h.output);out.setToolTip('F11 · 切換獨立輸出')
        spacer=QWidget();spacer.setObjectName('ToolbarSpacer');spacer.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred);bar.addWidget(spacer)
        bar.addWidget(QLabel(' 風格 '));self.theme_combo=QComboBox();self.theme_combo.addItems(NAMES);self.theme_combo.setMinimumWidth(115);bar.addWidget(self.theme_combo)
        bar.addWidget(QLabel(' 配置 '));self.layout_combo=QComboBox();self.layout_combo.addItems(NAMES);self.layout_combo.setMinimumWidth(115);bar.addWidget(self.layout_combo)
        self.theme_combo.currentIndexChanged.connect(self.apply_theme);self.layout_combo.currentIndexChanged.connect(self.apply_layout)
        h.setAcceptDrops(True)
    def finish(self,c):
        h=self.host;self.docks.append(c);self.cue_panel=CuePanel(c);self.cue_dock=self.dock('CueDock','CUE · 場景',self.cue_panel,Qt.BottomDockWidgetArea)
        from audio_meter import AudioMeter
        from audio_mixer import AudioPanel
        c.meter=AudioMeter(h);self.audio_panel=AudioPanel(h,c.meter);h.audio_mixer=self.audio_panel.mixer;self.audio_dock=self.dock('AudioDock','音訊監看／影片 FADER',self.audio_panel,Qt.RightDockWidgetArea)
        for d in self.docks:self.view_menu.addAction(d.toggleViewAction())
        self.view_menu.addSeparator();action(self.view_menu,'預覽視窗',h.show_preview)
        self.apply_theme(self.preferences.value('theme',0,type=int),save=False);self.apply_layout(self.preferences.value('layout',0,type=int),save=False)
    def toggle_dock(self,d):
        if d.isVisible() and not d.visibleRegion().isEmpty():d.hide()
        else:d.show();d.raise_()
    def reset(self):self.apply_theme(0);self.apply_layout(0)
    def apply_theme(self,index,save=True):
        if not 0<=index<len(NAMES):index=0
        self.theme_index=index;p=dict(PALETTES[index]);h=self.host
        p['check_image']=(Path(__file__).resolve().parent/'assets'/('check-dark.svg' if index in (0,2) else 'check-light.svg')).as_posix()
        p['check_disabled']=(Path(__file__).resolve().parent/'assets'/'check-disabled.svg').as_posix()
        self.theme_combo.blockSignals(True);self.theme_combo.setCurrentIndex(index);self.theme_combo.blockSignals(False);self.theme_actions[index].setChecked(True)
        css='''
        QMainWindow,QWidget { background: %(bg)s; color: %(text)s; font-family: "Microsoft JhengHei", "PingFang TC", sans-serif; font-size: 13px; }
        QWidget[panel="true"],QDockWidget::title,QMenuBar,QToolBar { background: %(panel)s; }
        QLabel,QWidget#ToolbarSpacer { background: transparent; }
        QLabel#SecondaryLabel,QLabel#TimeLabel { color: %(dim)s; font-size: 12px; }
        QLabel#BrandLabel { color: %(accent)s; font-weight: 600; letter-spacing: 1px; }
        QLabel#PanelHeading { font-weight: 600; }
        QDockWidget { border: 1px solid %(line)s; }
        QDockWidget::title { padding: 8px 10px; border-bottom: 1px solid %(line)s; }
        QToolBar { spacing: 5px; border: none; border-bottom: 1px solid %(line)s; padding: 7px 5px; }
        QPushButton,QToolButton { background: %(raised)s; color: %(text)s; border: 1px solid %(line)s; border-radius: 6px; padding: 7px 9px; }
        QPushButton:hover,QToolButton:hover { border-color: %(accent)s; }
        QPushButton#PrimaryButton,QPushButton#NextCueButton { background: %(accent)s; color: %(ink)s; border-color: %(accent)s; font-weight: 600; }
        QPushButton#StopButton { color: #d66b76; }
        QComboBox,QDoubleSpinBox,QLineEdit { background: %(bg)s; border: 1px solid %(line)s; border-radius: 5px; padding: 6px; selection-background-color: %(accent)s; selection-color: %(ink)s; }
        QComboBox::drop-down { border: none; width: 20px; }
        QListWidget,QListView { background: %(panel)s; border: 1px solid %(line)s; border-radius: 5px; outline: none; }
        QListWidget::item,QListView::item { padding: 10px 8px; border-bottom: 1px solid %(line)s; }
        QListWidget::item:selected,QListView::item:selected { background: %(raised)s; color: %(text)s; border-left: 3px solid %(accent)s; }
        QTabWidget::pane { border: 1px solid %(line)s; background: %(panel)s; }
        QTabBar::tab { background: %(panel)s; color: %(dim)s; padding: 9px 12px; border-bottom: 2px solid transparent; }
        QTabBar::tab:selected { color: %(text)s; border-bottom: 2px solid %(accent)s; }
        QSlider::groove:horizontal { height: 5px; background: %(raised)s; border-radius: 2px; }
        QSlider::sub-page:horizontal { background: %(accent)s; border-radius: 2px; }
        QSlider::handle:horizontal { background: %(accent)s; width: 13px; margin: -4px 0; border-radius: 6px; }
        QWidget#ChannelStrip { background: %(panel)s; border: 1px solid %(line)s; border-radius: 5px; }
        QLabel#FaderReadout { color: %(accent)s; font-family: Consolas, monospace; font-weight: 600; }
        QSlider#ChannelFader::groove:vertical { width: 8px; background: %(bg)s; border: 1px solid %(line)s; border-radius: 3px; }
        QSlider#ChannelFader::sub-page:vertical { background: %(raised)s; border-radius: 3px; }
        QSlider#ChannelFader::add-page:vertical { background: %(accent)s; border-radius: 3px; }
        QSlider#ChannelFader::handle:vertical { height: 20px; margin: 0 -11px; background: #e8eef3; border: 2px solid #526675; border-radius: 3px; }
        QPushButton#ChannelMute { padding: 6px 2px; font-size: 11px; }
        QPushButton#ChannelMute:checked { background: #b4384c; border-color: #ed7387; color: #ffffff; font-weight: 600; }
        QScrollArea { border: none; }
        QScrollBar:vertical { background: %(bg)s; width: 10px; }
        QScrollBar::handle:vertical { background: %(line)s; min-height: 24px; border-radius: 4px; }
        QMenu { background: %(panel)s; border: 1px solid %(line)s; padding: 5px; }
        QMenu::item { padding: 7px 22px; }
        QMenu::item:selected,QMenuBar::item:selected { background: %(raised)s; }
        QCheckBox { spacing: 10px; background: transparent; min-height: 28px; padding: 2px 0; }
        QCheckBox::indicator { width: 20px; height: 20px; border: 2px solid %(dim)s; border-radius: 4px; background: %(bg)s; }
        QCheckBox::indicator:checked { background: %(accent)s; border-color: %(accent)s; image: url("%(check_image)s"); }
        QCheckBox::indicator:unchecked:hover,QCheckBox::indicator:unchecked:focus { border-color: %(accent)s; background: %(raised)s; }
        QCheckBox::indicator:checked:hover,QCheckBox::indicator:checked:focus { border-color: %(text)s; }
        QCheckBox::indicator:pressed { border-color: %(text)s; }
        QCheckBox:disabled { color: %(dim)s; }
        QCheckBox::indicator:disabled { background: %(raised)s; border-color: %(line)s; }
        QCheckBox::indicator:checked:disabled { image: url("%(check_disabled)s"); }
        QToolTip { color: %(text)s; background: %(panel)s; border: 1px solid %(line)s; padding: 5px; }
        '''%p
        h.setStyleSheet(css)
        if hasattr(h,'compositor') and hasattr(h.compositor,'meter'):h.compositor.meter.set_colors(p)
        if save:self.preferences.setValue('theme',index);self.preferences.sync()
    def apply_layout(self,index,save=True):
        if not 0<=index<len(NAMES):index=0
        if not hasattr(self,'cue_dock'):return
        self.layout_index=index;h=self.host;c=h.compositor;asset=self.asset_dock;cue=self.cue_dock;audio=self.audio_dock
        self.layout_combo.blockSignals(True);self.layout_combo.setCurrentIndex(index);self.layout_combo.blockSignals(False);self.layout_actions[index].setChecked(True)
        h.setUpdatesEnabled(False)
        try:
            for d in self.docks:d.setFloating(False);h.removeDockWidget(d);d.setMinimumSize(180,100);d.setMaximumSize(16777215,16777215)
            c.tabs.show();self.audio_panel.set_performance(index==2);self.cue_panel.set_performance(index==2)
            h.setCorner(Qt.BottomLeftCorner,Qt.LeftDockWidgetArea if index in (0,1) else Qt.BottomDockWidgetArea)
            h.setCorner(Qt.BottomRightCorner,Qt.BottomDockWidgetArea)
            if index==0:
                h.addDockWidget(Qt.LeftDockWidgetArea,asset);h.addDockWidget(Qt.RightDockWidgetArea,audio);h.splitDockWidget(audio,c,Qt.Vertical);h.addDockWidget(Qt.BottomDockWidgetArea,cue)
                h.resizeDocks([asset,audio],[270,320],Qt.Horizontal);h.resizeDocks([audio,c],[210,440],Qt.Vertical);h.resizeDocks([cue],[180],Qt.Vertical)
            elif index==1:
                h.addDockWidget(Qt.LeftDockWidgetArea,asset);h.splitDockWidget(asset,cue,Qt.Vertical);h.addDockWidget(Qt.BottomDockWidgetArea,audio);h.splitDockWidget(audio,c,Qt.Horizontal)
                h.resizeDocks([asset],[285],Qt.Horizontal);h.resizeDocks([asset,cue],[430,280],Qt.Vertical);h.resizeDocks([audio,c],[290,700],Qt.Horizontal);h.resizeDocks([audio],[235],Qt.Vertical)
            elif index==2:
                h.addDockWidget(Qt.LeftDockWidgetArea,asset);h.addDockWidget(Qt.RightDockWidgetArea,c);h.addDockWidget(Qt.RightDockWidgetArea,audio);h.addDockWidget(Qt.BottomDockWidgetArea,cue)
                audio.setMinimumWidth(130);h.resizeDocks([audio],[140],Qt.Horizontal);h.resizeDocks([cue],[210],Qt.Vertical)
            else:
                h.addDockWidget(Qt.RightDockWidgetArea,asset);h.splitDockWidget(asset,audio,Qt.Vertical);h.tabifyDockWidget(asset,cue);h.tabifyDockWidget(asset,c)
                h.resizeDocks([asset],[340],Qt.Horizontal);h.resizeDocks([asset,audio],[500,200],Qt.Vertical)
            for d in self.docks:d.show()
            if index==2:asset.hide();c.hide()
            if index==3:asset.raise_()
        finally:h.setUpdatesEnabled(True)
        if hasattr(h,'screen'):h.screen.refit()
        if save:self.preferences.setValue('layout',index);self.preferences.sync()
    def refresh_info(self):
        h=self.host;r=h.screen.sceneRect();self.canvas_label.setText(f'{int(r.width())} × {int(r.height())}')
        if not hasattr(h,'compositor'):return
        if hasattr(h,'presentations') and h.presentations.active:
            state=h.presentations.native_state;self.source_label.setText('PowerPoint · '+media_name(h.current_item()));self.time_label.setText(f"投影片 {state.get('slide',1)} / {state.get('total',1)} · 動畫 {state.get('click',0)}");return
        if h.compositor.enabled:
            l=h.compositor.selected()
            d=l.decks[l.active] if l and l.c['kind']=='playlist' else None
            self.source_label.setText('多畫面 · '+(l.c['name'] if l else '請選取格子'))
        else:
            d=h.decks[h.active] if h.current is not None else None
            self.source_label.setText(media_name(d.config) if d and d.config else '尚未播放')
        if d and d.kind=='pdf':
            self.time_label.setText(f'PDF 第 {d.pdf_source.page+1} / {d.pdf_source.count} 頁');return
        if d:
            current=d.player.position() if d.kind=='video' else int((l.elapsed if h.compositor.enabled and l else h.elapsed)*1000)
            total=d.player.duration() if d.kind=='video' else int(d.config.get('seconds',5)*1000)
            fmt=lambda ms:f'{max(0,int(ms))//60000:02d}:{max(0,int(ms))//1000%60:02d}'
            self.time_label.setText(fmt(current)+' / '+fmt(total))
        else:self.time_label.setText('00:00 / 00:00')
