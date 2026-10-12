"""Clip playback editor with asynchronous native audio waveform decoding."""
import math,struct
from pathlib import Path
from PySide6.QtCore import Qt,QUrl,QTimer,Signal
from PySide6.QtGui import QPainter,QColor,QPen
from PySide6.QtWidgets import (QDialog,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
    QSlider,QDoubleSpinBox,QCheckBox,QDialogButtonBox,QMessageBox)
from PySide6.QtMultimedia import QMediaPlayer,QAudioOutput,QAudioDecoder,QAudioFormat
from PySide6.QtMultimediaWidgets import QVideoWidget

class Waveform(QWidget):
    seek=Signal(float)
    def __init__(self,parent=None):
        super().__init__(parent);self.setMinimumHeight(120);self.duration=1.;self.position=0.;self.start=0.;self.end=0.;self.points={};self.setCursor(Qt.PointingHandCursor)
    def add_buffer(self,buffer):
        fmt=buffer.format();raw=bytes(buffer.data());kind=fmt.sampleFormat()
        specs={QAudioFormat.UInt8:('B',1,128.),QAudioFormat.Int16:('h',2,32768.),QAudioFormat.Int32:('i',4,2147483648.),QAudioFormat.Float:('f',4,1.)}
        if kind not in specs:return
        code,size,scale=specs[kind];count=len(raw)//size
        if not count:return
        # Sample across each decoded buffer rather than blocking the UI on every sample.
        stride=max(1,count//1024);peak=0.
        for i in range(0,count,stride):
            value=struct.unpack_from('='+code,raw,i*size)[0]
            value=(value-128)/scale if code=='B' else value/scale
            if math.isfinite(value):peak=max(peak,min(1.,abs(value)))
        t=max(0,buffer.startTime()/1000000)
        self.points[t]=max(peak,self.points.get(t,0.));self.update()
    def paintEvent(self,event):
        p=QPainter(self);w,h=self.width(),self.height();p.fillRect(self.rect(),QColor('#0d1623'))
        total=max(self.duration,max(self.points,default=0.)+.1,1.)
        end=self.end if self.end>0 else total
        p.fillRect(int(w*self.start/total),0,max(0,int(w*(end-self.start)/total)),h,QColor('#193e45'))
        bins=[0.]*max(1,w)
        for t,peak in self.points.items():
            x=min(w-1,max(0,int(w*t/total)));bins[x]=max(bins[x],peak)
        p.setPen(QColor('#6ee7d4'))
        for x,peak in enumerate(bins):
            amp=max(1,int(peak*(h/2-8)));p.drawLine(x,int(h/2)-amp,x,int(h/2)+amp)
        p.setPen(QPen(QColor('#ffcd70'),2));x=int(w*self.position/total);p.drawLine(x,0,x,h)
    def mousePressEvent(self,e):
        self.seek.emit(max(0,min(self.duration,e.position().x()/max(1,self.width())*self.duration)))

class VideoEditor(QDialog):
    def __init__(self,path,config,parent=None):
        super().__init__(parent);self.setWindowTitle('編輯影片 — '+Path(path).name);self.resize(1000,760);self.result_config=None
        self.player=QMediaPlayer(self);self.audio=QAudioOutput(self);self.player.setAudioOutput(self.audio)
        self.decoder=QAudioDecoder(self);self.total=0;self.previewing=False
        v=QVBoxLayout(self);self.video=QVideoWidget();self.video.setMinimumHeight(300);v.addWidget(self.video,1);self.player.setVideoOutput(self.video)
        self.wave=Waveform();v.addWidget(self.wave);self.wave.seek.connect(lambda seconds:self.player.setPosition(int(seconds*1000)))
        self.message=QLabel('正在分析音訊波形；沒有音軌或不支援解碼時仍可編輯片段。');v.addWidget(self.message)
        self.seek=QSlider(Qt.Horizontal);self.seek.setRange(0,10000);v.addWidget(self.seek);self.seek.sliderMoved.connect(lambda n:self.player.setPosition(int(self.total*n/10000)))
        row=QHBoxLayout();v.addLayout(row)
        for name,fn in [('播放／暫停',self.toggle),('預覽剪輯片段',self.preview),('設為起點',lambda:self.start.setValue(self.player.position()/1000)),('設為終點',lambda:self.end.setValue(self.player.position()/1000))]:
            b=QPushButton(name);b.clicked.connect(lambda checked=False,f=fn:f());row.addWidget(b)
        self.time=QLabel('00:00 / 00:00');row.addWidget(self.time)
        row=QHBoxLayout();v.addLayout(row)
        self.start=QDoubleSpinBox();self.end=QDoubleSpinBox()
        for label,spin,value in [('起點（秒）',self.start,config.get('start',0)),('終點（0＝播至結尾）',self.end,config.get('end',0))]:
            spin.setRange(0,86400);spin.setDecimals(2);spin.setValue(value);row.addWidget(QLabel(label));row.addWidget(spin);spin.valueChanged.connect(self.trim_changed)
        row=QHBoxLayout();v.addLayout(row);row.addWidget(QLabel('音量 %'));self.volume=QSlider(Qt.Horizontal);self.volume.setRange(0,100);self.volume.setValue(int(config.get('gain',100)));row.addWidget(self.volume)
        self.volume_text=QLabel();row.addWidget(self.volume_text);self.mute=QCheckBox('靜音');self.mute.setChecked(config.get('mute',False));row.addWidget(self.mute)
        self.volume.valueChanged.connect(self.update_audio);self.mute.toggled.connect(self.update_audio);self.update_audio()
        v.addWidget(QLabel('波形顯示原始音軌振幅，黃色線為播放位置，底色為保留片段。套用後更新播放設定，原始檔案不會被覆寫。'))
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText('套用編輯');buttons.button(QDialogButtonBox.Cancel).setText('取消');v.addWidget(buttons);buttons.accepted.connect(self.apply);buttons.rejected.connect(self.reject)
        self.player.durationChanged.connect(self.duration_changed);self.player.positionChanged.connect(self.position_changed)
        self.player.errorOccurred.connect(lambda code,msg:self.message.setText('影片播放失敗：'+msg))
        self.decoder.bufferReady.connect(self.read_audio);self.decoder.finished.connect(self.decoded);self.decoder.error.connect(lambda *args:self.message.setText('音訊波形無法解碼；仍可設定播放片段與音量。'))
        self.trim_changed();url=QUrl.fromLocalFile(path);self.player.setSource(url);self.decoder.setSource(url);self.decoder.start()
    def update_audio(self,*_):
        self.audio.setVolume(self.volume.value()/100);self.audio.setMuted(self.mute.isChecked());self.volume_text.setText(str(self.volume.value()))
    def trim_changed(self,*_):
        self.wave.start=self.start.value();self.wave.end=self.end.value();self.wave.update()
    def duration_changed(self,n):
        self.total=n;self.wave.duration=max(1,n/1000);self.wave.update()
        if n>0:self.start.setMaximum(max(0,n/1000-.01));self.end.setMaximum(n/1000)
    def position_changed(self,n):
        self.wave.position=n/1000;self.wave.update()
        if not self.seek.isSliderDown():self.seek.setValue(int(n/max(1,self.total)*10000))
        self.time.setText(f'{n/1000:.2f} / {self.total/1000:.2f} 秒')
        end=int(self.end.value()*1000) if self.end.value()>0 else self.total
        if self.previewing and end>0 and n>=end:self.player.pause();self.previewing=False
    def toggle(self):
        self.previewing=False
        if self.player.playbackState()==QMediaPlayer.PlayingState:self.player.pause()
        else:self.player.play()
    def preview(self):
        if self.end.value()>0 and self.end.value()<=self.start.value():self.invalid();return
        self.previewing=True;self.player.setPosition(int(self.start.value()*1000));self.player.play()
    def invalid(self):QMessageBox.warning(self,'片段設定錯誤','終點必須大於起點，或填 0 表示播至結尾。')
    def read_audio(self):
        if self.decoder.bufferAvailable():self.wave.add_buffer(self.decoder.read())
    def decoded(self):self.message.setText('音訊波形分析完成。' if self.wave.points else '此影片沒有可解碼的音訊波形。')
    def apply(self):
        if self.end.value()>0 and self.end.value()<=self.start.value():self.invalid();return
        self.result_config={'start':self.start.value(),'end':self.end.value(),'gain':self.volume.value(),'mute':self.mute.isChecked()};self.accept()
    def done(self,result):
        self.decoder.stop();self.player.stop();super().done(result)
