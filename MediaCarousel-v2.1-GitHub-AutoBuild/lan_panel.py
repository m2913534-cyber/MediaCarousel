"""內網投影 window: start the LEDSpace-compatible receiver and add connected computers as sources."""
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QListWidget,QListWidgetItem,QFrame

class LanPanel(QDialog):
    def __init__(self,host):
        super().__init__(host);self.host=host;self.hub=host.lan_hub
        self.setWindowTitle('內網投影 — LEDSpace Sender');self.setMinimumWidth(460)
        v=QVBoxLayout(self);v.setSpacing(10)
        intro=QLabel('其他電腦開啟 LEDSpace Sender，填入下方「接收端位址」與「配對碼」，傳輸模式選「TCP 相容」，再選擇要分享的螢幕。')
        intro.setWordWrap(True);intro.setObjectName('SecondaryLabel');v.addWidget(intro)
        r=QHBoxLayout();v.addLayout(r)
        self.toggle=QPushButton();self.toggle.setObjectName('PrimaryButton');self.toggle.clicked.connect(self.switch);r.addWidget(self.toggle)
        self.state=QLabel();r.addWidget(self.state,1)
        box=QFrame();box.setObjectName('ChannelStrip');b=QVBoxLayout(box);v.addWidget(box)
        b.addWidget(QLabel('接收端位址'))
        self.addresses=QLabel();self.addresses.setTextInteractionFlags(Qt.TextSelectableByMouse);self.addresses.setStyleSheet('font-size:18px;font-weight:600;');b.addWidget(self.addresses)
        b.addWidget(QLabel('配對碼'))
        r=QHBoxLayout();b.addLayout(r)
        self.code=QLabel();self.code.setTextInteractionFlags(Qt.TextSelectableByMouse);self.code.setStyleSheet('font-size:26px;font-weight:700;letter-spacing:2px;');r.addWidget(self.code,1)
        self.copy=QPushButton('複製位址與配對碼');self.copy.clicked.connect(self.copy_info);r.addWidget(self.copy)
        v.addWidget(QLabel('已連線的電腦'))
        self.list=QListWidget();self.list.setMinimumHeight(140);self.list.itemDoubleClicked.connect(lambda _:self.add());v.addWidget(self.list,1)
        r=QHBoxLayout();v.addLayout(r)
        self.add_button=QPushButton('＋ 加入目前清單');self.add_button.clicked.connect(self.add);r.addWidget(self.add_button)
        r.addStretch()
        note=QLabel('限 TCP 相容模式：最高 1080p、無聲音；請使用有線內網。來源斷線時畫面停在最後一格。第一次啟動時 macOS 可能詢問是否允許接收連線，請選「允許」。')
        note.setWordWrap(True);note.setObjectName('SecondaryLabel');v.addWidget(note)
        self.hub.changed.connect(self.refresh);self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(1000);self.refresh()
    def switch(self):
        try:
            if self.hub.running:self.hub.stop();self.host.status.setText('內網接收已停止')
            else:port=self.hub.start();self.host.status.setText(f'內網接收已啟動（埠 {port}）')
        except OSError as e:self.host.status.setText(str(e));self.state.setText(str(e))
        self.refresh()
    def copy_info(self):
        QGuiApplication.clipboard().setText('接收端位址：'+'、'.join(self.hub.addresses())+'\n配對碼：'+self.hub.code)
        self.host.status.setText('已複製位址與配對碼')
    def refresh(self,*_):
        running=self.hub.running
        self.toggle.setText('停止內網接收' if running else '啟動內網接收')
        self.state.setText(f'● 接收中（埠 {self.hub.port}）' if running else '○ 未啟動')
        addresses=self.hub.addresses() if running else []
        self.addresses.setText('\n'.join(addresses) if addresses else ('找不到內網位址，請確認網路線或 Wi-Fi' if running else '—'))
        self.code.setText(self.hub.code if running else '—');self.copy.setEnabled(running)
        selected=self.list.currentItem().data(Qt.UserRole) if self.list.currentItem() else None
        self.list.clear()
        for s in self.hub.senders() if running else []:
            if s['transport']!='tcp':status='WebRTC — 請在 Sender 改選「TCP 相容」'
            elif s['live']:status=f"{s['fps']:.0f} FPS · {s['width']}×{s['height']}（目標 {s['target_fps']} FPS）"
            else:status='已連線，等待畫面'
            item=QListWidgetItem(f"{s['name']}　{status}");item.setData(Qt.UserRole,(s['key'],s['name']));self.list.addItem(item)
            if selected and selected[0]==s['key']:self.list.setCurrentItem(item)
        if self.list.count() and not self.list.currentItem():self.list.setCurrentRow(0)
        self.add_button.setEnabled(self.list.currentItem() is not None)
    def add(self):
        item=self.list.currentItem()
        if item:key,name=item.data(Qt.UserRole);self.host.add_lan(key,name)

def open_panel(host):
    if getattr(host,'lan_panel',None) is None:host.lan_panel=LanPanel(host)
    host.lan_panel.show();host.lan_panel.raise_();host.lan_panel.activateWindow();host.lan_panel.refresh()
