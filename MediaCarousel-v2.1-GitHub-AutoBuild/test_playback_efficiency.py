"""Regression checks for lossless PCM analysis and work avoided during playback."""
import os,math,random,struct,tempfile
os.environ['QT_QPA_PLATFORM']='offscreen'
from unittest.mock import patch
from PySide6.QtCore import QByteArray,QSettings
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QAudioBuffer,QAudioFormat,QAudioOutput
from audio_meter import levels
from live_audio import LiveAudio
from app import Window

app=QApplication([])
rng=random.Random(27)
for sf,code,low,high,scale,offset in [
    (QAudioFormat.UInt8,'B',0,255,128,128),
    (QAudioFormat.Int16,'h',-32768,32767,32768,0),
    (QAudioFormat.Int32,'i',-2147483648,2147483647,2147483648,0),
    (QAudioFormat.Float,'f',-1.,1.,1,0)]:
    for channels in (1,2,6):
        values=[rng.uniform(low,high) if code=='f' else rng.randint(low,high) for _ in range(4096*channels)]
        values[:channels]=[low]*channels;values[-channels:]=[high]*channels
        raw=struct.pack('<'+code*len(values),*values);values=struct.unpack('<'+code*len(values),raw)
        fmt=QAudioFormat();fmt.setSampleRate(48000);fmt.setChannelCount(channels);fmt.setSampleFormat(sf)
        peak,rms=levels(QAudioBuffer(QByteArray(raw),fmt))
        for channel in range(2):
            samples=[abs((v-offset)/scale) for v in values[(channel if channels>1 else 0)::channels]]
            assert abs(peak[channel]-max(samples))<1e-12
            assert abs(rms[channel]-math.sqrt(math.fsum(v*v for v in samples)/len(samples)))<1e-12
assert levels(QAudioBuffer())==([0,0],[0,0])

audio=QAudioOutput();state=LiveAudio(audio)
with patch.object(audio,'setVolume',wraps=audio.setVolume) as volume,patch.object(audio,'setMuted',wraps=audio.setMuted) as mute:
    for _ in range(1000):state.apply(1/3,False)
    assert volume.call_count==mute.call_count==1 # avoid float32 equality traps
    for n in range(1,101):state.apply(n/100,False)
    assert volume.call_count==101 and mute.call_count==1 # every fade step retained
    state.apply(1,True);assert audio.isMuted() and mute.call_count==2
    audio.setMuted(False);audio.setVolume(.2);state.apply(1,True)
    assert audio.isMuted() and abs(audio.volume()-1)<1e-6 # external changes invalidate cache

with tempfile.TemporaryDirectory() as folder,patch('interface.QSettings',lambda *a:QSettings(folder+'/prefs.ini',QSettings.IniFormat)):
    w=Window();w.session_ready=False;w.session_timer.stop();c=w.compositor;c.grid(4,3);c.list.setCurrentRow(0);layer=c.selected()
    before=(layer.rect(),layer.pos());layouts=[]
    with patch.object(layer.decks[0],'layout',wraps=layer.decks[0].layout) as first,patch.object(layer.decks[1],'layout',wraps=layer.decks[1].layout) as second:
        for gain in range(1,101):c.controls['gain'].setValue(gain)
        c.mute.setChecked(True);c.mute.setChecked(False)
        assert first.call_count==second.call_count==0
        assert before==(layer.rect(),layer.pos())
        c.controls['w'].setValue(layer.c['w']+50)
        assert first.call_count==second.call_count==1
    w.close()
print('PASS all PCM samples/formats/channels within 1e-12; 1000 steady audio polls -> 1 write/property; all 100 fade steps; live mute and external invalidation; 12-layer audio edits avoid geometry work')
