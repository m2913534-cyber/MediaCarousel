"""Live, per-playback-source faders. Eligibility uses decoded stream metadata."""
import math
from dataclasses import dataclass
from PySide6.QtCore import Qt,QTimer,Signal
from PySide6.QtGui import QPainter,QFont
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QBoxLayout,QLabel,QSlider,QPushButton,QScrollArea
from model import media_name,number

def fader_gain(value):return 0 if value<=0 else 100*10**((value/1000*60-60)/20)
def gain_fader(gain):return 0 if gain<=0 else max(1,min(1000,round((20*math.log10(gain/100)+60)/60*1000)))

@dataclass
class Binding:
    deck:object
    layer:object
    label:str
    def __post_init__(self):self.source=self.deck.source_ref
    @property
    def key(self):return (id(self.deck),id(self.source))
    @property
    def muted(self):return bool(self.deck.config.get('mute') or self.layer is not None and self.layer.c.get('mute'))

class DecibelScale(QWidget):
    def __init__(self):super().__init__();self.setFixedWidth(29)
    def paintEvent(self,event):
        p=QPainter(self);p.setFont(QFont('Consolas',8));p.setPen(self.palette().color(self.foregroundRole()));height=max(1,self.height()-22)
        for db in [0,-12,-24,-36,-48,-60]:p.drawText(0,round(14+(-db/60)*height),str(db))

class ChannelStrip(QWidget):
    def __init__(self,mixer,binding):
        super().__init__();self.mixer=mixer;self.binding=binding;self.setObjectName('ChannelStrip');self.setFixedWidth(112)
        v=QVBoxLayout(self);v.setContentsMargins(7,7,7,7);v.setSpacing(5)
        self.channel=QLabel();self.channel.setObjectName('PanelHeading');self.channel.setAlignment(Qt.AlignCenter);v.addWidget(self.channel)
        self.name=QLabel();self.name.setAlignment(Qt.AlignCenter);v.addWidget(self.name)
        self.readout=QLabel();self.readout.setAlignment(Qt.AlignCenter);self.readout.setObjectName('FaderReadout');v.addWidget(self.readout)
        r=QHBoxLayout();r.setSpacing(2);v.addLayout(r,1);r.addWidget(DecibelScale());self.slider=QSlider(Qt.Vertical);self.slider.setObjectName('ChannelFader');self.slider.setRange(0,1000);self.slider.setMinimumHeight(90);self.slider.setTickPosition(QSlider.TicksBothSides);self.slider.setTickInterval(200);self.slider.setPageStep(50);self.slider.setSingleStep(5);r.addWidget(self.slider,1)
        self.percent=QLabel();self.percent.setObjectName('SecondaryLabel');self.percent.setAlignment(Qt.AlignCenter);v.addWidget(self.percent)
        self.mute=QPushButton('MUTE · 靜音');self.mute.setObjectName('ChannelMute');self.mute.setCheckable(True);self.mute.setToolTip('即時靜音／解除靜音，保持影片目前播放位置。');v.addWidget(self.mute)
        self.slider.setAccessibleName('影片音量推桿');self.mute.setAccessibleName('影片即時靜音')
        self.slider.valueChanged.connect(lambda value:mixer.set_audio(self.binding,gain=fader_gain(value)));self.slider.sliderReleased.connect(mixer.host.persist_session)
        self.mute.toggled.connect(lambda value:mixer.set_audio(self.binding,mute=value,persist=True));self.refresh()
    def refresh(self):
        b=self.binding;gain=number(b.deck.config.get('gain',100),100,0,100);db=20*math.log10(gain/100) if gain>0 else None
        self.channel.setText(b.label);name=media_name(b.deck.config);self.name.setText(self.name.fontMetrics().elidedText(name,Qt.ElideMiddle,94));self.name.setToolTip(b.deck.config.get('path',name))
        self.readout.setText(f'{db:.1f} dB' if db is not None else '−∞ dB');self.percent.setText(f'{gain:.1f}%')
        self.slider.setToolTip('素材音量；主音量與格子音量仍會共同作用。')
        if not self.slider.isSliderDown():self.slider.blockSignals(True);self.slider.setValue(gain_fader(gain));self.slider.blockSignals(False)
        self.mute.blockSignals(True);self.mute.setChecked(b.muted);self.mute.blockSignals(False)

class AudioMixer(QWidget):
    contentChanged=Signal()
    def __init__(self,host):
        super().__init__();self.host=host;self.strips={};self.setObjectName('AudioMixer');self.setMinimumHeight(300)
        v=QVBoxLayout(self);v.setContentsMargins(0,8,0,0);v.setSpacing(6);heading=QLabel('LIVE AUDIO · 影片 FADER');heading.setObjectName('PanelHeading');v.addWidget(heading)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.scroll.setMinimumSize(145,260);v.addWidget(self.scroll)
        self.body=QWidget();self.channels=QHBoxLayout(self.body);self.channels.setContentsMargins(0,0,0,0);self.channels.setSpacing(6);self.channels.addStretch();self.scroll.setWidget(self.body)
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(100);self.hide()
    def bindings(self):
        h=self.host
        if hasattr(h,'presentations') and h.presentations.active:return []
        contexts=[(layer,layer.decks,layer.active,layer.current,layer.transition) for layer in h.compositor.layers if layer.c['kind']=='playlist'] if h.compositor.enabled else [(None,h.decks,h.active,h.current,h.transition)]
        result=[]
        for layer,decks,active,current,transition in contexts:
            if current is None:continue
            if transition:indices=[transition[1],transition[0]] if layer else [transition['old'],transition['new']]
            else:indices=[active]
            for index in indices:
                deck=decks[index]
                if deck.source_ref is None or deck.kind!='video' or not deck.player.hasAudio() or not deck.player.hasVideo():continue
                label=f'CH {h.compositor.layers.index(layer)+1:02d}' if layer else '單畫面'
                if transition:label+=' · 淡入' if index==indices[-1] else ' · 淡出'
                result.append(Binding(deck,layer,label))
        return result
    def refresh(self):
        bindings=self.bindings();keys={b.key for b in bindings};had_channels=bool(self.strips)
        for key in list(self.strips):
            if key not in keys:
                strip=self.strips.pop(key);self.channels.removeWidget(strip);strip.hide();strip.deleteLater()
        for index,b in enumerate(bindings):
            if b.key not in self.strips:
                strip=ChannelStrip(self,b);self.strips[b.key]=strip;self.channels.insertWidget(index,strip)
            strip=self.strips[b.key];strip.binding=b;strip.refresh()
        self.scroll.setMinimumWidth(230 if len(bindings)>1 else 145)
        if bindings:
            if not had_channels:self.contentChanged.emit()
            self.show()
        else:
            self.hide()
            if had_channels:self.contentChanged.emit()
    def set_audio(self,binding,gain=None,mute=None,persist=False):
        # A stale queued UI event must never alter a reused deck's next source.
        if binding.deck.source_ref is not binding.source or not any(b.key==binding.key for b in self.bindings()):return
        changes={}
        if gain is not None:changes['gain']=number(gain,100,0,100)
        if mute is not None:
            changes['mute']=bool(mute)
            if not mute and binding.layer is not None:
                binding.layer.c['mute']=False
                if self.host.compositor.selected() is binding.layer:self.host.compositor.sync_controls()
        binding.deck.config.update(changes);binding.deck.source_ref.update(changes);self.host.refresh_live_audio();self.host.sync_selected_audio();self.refresh()
        if persist:self.host.persist_session()

class AudioPanel(QWidget):
    def __init__(self,host,meter):
        super().__init__();self.performance=False;self.meter=meter;self.mixer=AudioMixer(host);self.box=QBoxLayout(QBoxLayout.TopToBottom,self);self.box.setContentsMargins(8,6,8,6);self.box.setSpacing(4);self.box.addWidget(meter);self.box.addWidget(self.mixer,1);self.mixer.contentChanged.connect(self.relayout)
    def set_performance(self,on):
        self.performance=on;self.relayout()
    def relayout(self):
        vertical=self.performance or bool(self.mixer.strips);self.box.setDirection(QBoxLayout.LeftToRight if vertical else QBoxLayout.TopToBottom);self.meter.set_vertical(vertical)
