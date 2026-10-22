"""Decoded PCM sample-peak/RMS meter for the selected playback source (not system mix)."""
import math,time,array,sys
from PySide6.QtCore import Qt,QTimer,QRectF
from PySide6.QtGui import QPainter,QColor,QFont
from PySide6.QtWidgets import QWidget
from PySide6.QtMultimedia import QAudioBufferOutput,QAudioFormat,QMediaPlayer

def levels(buffer):
    fmt=buffer.format();channels=fmt.channelCount()
    specs={QAudioFormat.UInt8:('B',128,128),QAudioFormat.Int16:('h',32768,0),QAudioFormat.Int32:('i',2147483648,0),QAudioFormat.Float:('f',1,0)}
    spec=specs.get(fmt.sampleFormat())
    if not spec or not channels or not buffer.isValid():return [0,0],[0,0]
    code,scale,offset=spec;data=array.array(code);data.frombytes(bytes(buffer.constData())[:buffer.byteCount()])
    peaks=[];rms=[]
    for ch in range(min(2,channels)):
        values=[abs((v-offset)/scale) for v in data[ch::channels]]
        peaks.append(max(values,default=0));rms.append(math.sqrt(sum(v*v for v in values)/max(1,len(values))))
    if channels==1:peaks*=2;rms*=2
    return peaks,rms

class AudioProbe:
    def __init__(self,player):
        self.enabled=False;self.peak=[0,0];self.rms=[0,0];self.when=0
        self.output=QAudioBufferOutput(player);player.setAudioBufferOutput(self.output);self.output.audioBufferReceived.connect(self.receive)
    def receive(self,buffer):
        if self.enabled:
            self.peak,self.rms=levels(buffer);self.when=time.monotonic()

class AudioMeter(QWidget):
    def __init__(self,host):
        super().__init__();self.host=host;self.vertical=False;self.colors={'bg':'#091019','text':'#dce7ef','dim':'#8196a8','raised':'#1d2a36','accent':'#36d28b'};self.setMinimumHeight(165);self.setMaximumHeight(180)
        self.db=[-60.,-60.];self.rms=[-60.,-60.];self.hold=[-60.,-60.];self.until=[0.,0.];self.clip_until=0;self.probe=None;self.label='等待音訊';self.last=time.monotonic()
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(50)
    def set_colors(self,palette):
        self.colors=dict(palette);self.update()
    def set_vertical(self,on):
        self.vertical=on;self.setMinimumSize(110 if on else 180,300 if on else 165);self.setMaximumHeight(16777215 if on else 180);self.update()
    def paint_vertical(self,p):
        width,height=self.width(),self.height();top,bottom=55,height-65;span=max(80,bottom-top)
        p.setPen(QColor(self.colors['text']));p.drawText(12,20,'L / R');p.setPen(QColor(self.colors['dim']));p.drawText(12,38,'dBFS · POST')
        for ch in range(2):
            x=14+ch*30
            for k in range(30):
                threshold=-60+2*k;color=self.colors['raised']
                if self.db[ch]>-60 and self.db[ch]>=threshold:color='#ff4757' if threshold>=-6 else '#ffc34d' if threshold>=-18 else '#36d28b'
                p.fillRect(QRectF(x,bottom-(k+1)*span/30,18,span/30-2),QColor(color))
            y=bottom-max(0,min(60,self.hold[ch]+60))/60*span;p.fillRect(QRectF(x-2,y,22,2),QColor(self.colors['text']))
            p.setPen(QColor(self.colors['text']));p.drawText(x+4,bottom+18,'LR'[ch]);p.setPen(QColor(self.colors['dim']));p.drawText(x-3,bottom+36,f'{self.db[ch]:.0f}')
        p.setPen(QColor(self.colors['dim']))
        for value in [0,-12,-24,-36,-48,-60]:p.drawText(78,int(bottom-(value+60)/60*span)+4,str(value))
        p.setPen(QColor('#ff4757') if time.monotonic()<self.clip_until else QColor(self.colors['dim']));p.drawText(12,height-9,'● CLIP' if time.monotonic()<self.clip_until else '○ CLIP')
    def refresh(self):
        h=self.host;now=time.monotonic();dt=min(1,now-self.last);self.last=now
        layer=h.compositor.selected() if h.compositor.enabled else None
        deck=None
        if layer is not None and layer.c['kind']=='playlist':deck=layer.decks[layer.transition[0] if layer.transition else layer.active]
        elif not h.compositor.enabled:deck=h.decks[h.transition['new'] if h.transition else h.active]
        probe=deck.probe if deck else None
        if self.probe is not probe:
            if self.probe:self.probe.enabled=False
            self.probe=probe;self.hold=[-60.,-60.];self.until=[0.,0.];self.clip_until=0
            if probe:probe.enabled=True
        has_audio=bool(deck and deck.kind=='video' and deck.player.hasAudio())
        self.label=('選取格子' if layer else '單畫面')+' · L/R · POST FADER' if has_audio else '目前來源無音訊'
        active=has_audio and deck.player.playbackState()==QMediaPlayer.PlayingState and now-probe.when<.3
        gain=deck.audio.volume() if active and not deck.audio.isMuted() else 0
        for i in range(2):
            peak=probe.peak[i]*gain if active else 0;rms=probe.rms[i]*gain if active else 0
            db=20*math.log10(max(peak,1e-6));self.db[i]=max(-60,db,self.db[i]-24*dt);self.rms[i]=max(-60,20*math.log10(max(rms,1e-6)))
            if db>=self.hold[i]:self.hold[i]=db;self.until[i]=now+1.5
            elif now>self.until[i]:self.hold[i]=max(-60,self.hold[i]-12*dt)
            if peak>=.999:self.clip_until=now+1.5
        self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor(self.colors['bg']));p.setFont(QFont('Consolas',9));p.setPen(QColor(self.colors['dim']))
        if self.vertical:self.paint_vertical(p);return
        p.drawText(10,18,self.label)
        p.drawText(10,36,'SAMPLE PEAK / RMS    dBFS')
        left=30;right=self.width()-12;span=right-left
        for ch in range(2):
            y=51+ch*37;p.setPen(QColor(self.colors['text']));p.drawText(10,y+14,'LR'[ch])
            for k in range(30):
                threshold=-60+2*k;color=self.colors['raised']
                if self.db[ch]>-60 and self.db[ch]>=threshold:color='#ff4757' if threshold>=-6 else '#ffc34d' if threshold>=-18 else '#36d28b'
                p.fillRect(QRectF(left+k*span/30,y,span/30-2,16),QColor(color))
            x=left+max(0,min(60,self.hold[ch]+60))/60*span;p.fillRect(QRectF(x-1,y-2,2,20),QColor(self.colors['text']))
            p.setPen(QColor(self.colors['dim']));p.drawText(left,y+30,f'PK {self.db[ch]:5.1f}   RMS {self.rms[ch]:5.1f}')
        p.setPen(QColor(self.colors['dim']))
        for db in [-60,-48,-36,-24,-12,0]:p.drawText(int(left+(db+60)/60*span)-10,137,str(db))
        p.setPen(QColor('#ff4757') if time.monotonic()<self.clip_until else QColor('#455464'));p.drawText(10,158,'● CLIP' if time.monotonic()<self.clip_until else '○ CLIP')
        p.setPen(QColor(self.colors['dim']));p.drawText(86,158,'選取來源／非系統總混音')
