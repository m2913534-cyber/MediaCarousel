"""Integration tests decode real audible/silent files and observe live player identity."""
import os,tempfile,time,subprocess,shutil,copy
os.environ['QT_QPA_PLATFORM']='offscreen'
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QSettings
from PySide6.QtGui import QImage,QColor
from PySide6.QtTest import QSignalSpy,QTest
from PySide6.QtMultimedia import QMediaPlayer
from app import Window,Deck
from compositor import MediaDeck
from audio_mixer import gain_fader,fader_gain
# No sound device exists in the test container. Decode through QAudioBufferOutput
# while checking the real QAudioOutput gain/mute properties without opening a device.
for deck_class in (Deck,MediaDeck):
    original_init=deck_class.__init__
    def headless_init(self,*args,_init=original_init,**kwargs):
        _init(self,*args,**kwargs);self.player.setAudioOutput(None)
    deck_class.__init__=headless_init
app=QApplication([])
def wait(fn):
    deadline=time.monotonic()+12
    while not fn() and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
    assert fn()
def settled(w):return not w.pending and not w.transition
assert shutil.which('ffmpeg'),'Integration fixture creation requires FFmpeg'
with tempfile.TemporaryDirectory() as folder:
    audio=folder+'/audible.mp4';silent=folder+'/silent.mp4';image=folder+'/still.png'
    for path,sound in [(audio,True),(silent,False)]:
        command=['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=blue:s=160x90:r=25:d=20']
        if sound:command+=['-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=20']
        subprocess.run(command+['-c:v','libx264','-threads','1','-pix_fmt','yuv420p']+(['-c:a','aac'] if sound else ['-an'])+['-y',path],check=True)
    im=QImage(200,100,QImage.Format_RGB32);im.fill(QColor('red'));im.save(image)
    with patch('interface.QSettings',lambda *a:QSettings(folder+'/prefs.ini',QSettings.IniFormat)):
        w=Window();w.session_ready=False;w.session_timer.stop();w.show();w.effect.setCurrentText('直接切換');w.mode.setCurrentText('單檔循環')
        w.lists=[{'name':'來源','items':[{'path':p,'seconds':60,'gain':100,'mute':False} for p in [audio,silent,image]]}];w.refresh_groups();w.files.setCurrentRow(0);w.play_selected();m=w.audio_mixer
        wait(lambda:settled(w) and len(m.strips)==1);d=w.decks[w.active];strip=next(iter(m.strips.values()));player=d.player;source_spy=QSignalSpy(player.sourceChanged)
        assert strip.slider.orientation()==Qt.Vertical and m.isVisible()
        before=player.position();QTest.mouseClick(strip.mute,Qt.LeftButton);assert d.audio.isMuted() and d.config['mute'] and w.lists[0]['items'][0]['mute']
        wait(lambda:player.position()>before+150);assert player.playbackState()==QMediaPlayer.PlayingState and source_spy.count()==0
        QTest.mouseClick(strip.mute,Qt.LeftButton);assert not d.audio.isMuted();strip.slider.setValue(gain_fader(50));assert abs(d.audio.volume()-.8*.5)<.003
        w.clip_mute.setChecked(True);assert d.audio.isMuted();w.clip_mute.setChecked(False);assert not d.audio.isMuted()
        w.clip_gain.setValue(44);assert abs(d.audio.volume()-.8*.44)<.001
        # Browsing a different muted asset must not mute the active source.
        w.lists[0]['items'][1]['mute']=True;w.files.setCurrentRow(1);assert not d.audio.isMuted();w.files.setCurrentRow(0)
        w.toggle();assert player.playbackState()==QMediaPlayer.PausedState;m.set_audio(strip.binding,mute=True);assert d.audio.isMuted() and len(m.strips)==1
        m.set_audio(strip.binding,mute=False);w.toggle();assert player is d.player and source_spy.count()==0
        # Stopped, silent and still sources produce no channel strip.
        old_binding=strip.binding;w.request((0,1));wait(lambda:settled(w) and not m.strips);assert m.isHidden()
        w.request((0,2));wait(lambda:settled(w) and not m.strips);assert m.isHidden()
        m.set_audio(old_binding,mute=True);assert not w.current_item().get('mute')
        # During a dissolve, controls remain bound to the outgoing/incoming source.
        w.request((0,0));wait(lambda:settled(w) and len(m.strips)==1)
        w.lists[0]['items'].append({'path':audio,'seconds':60,'gain':100,'mute':False});w.effect.setCurrentText('淡入淡出');w.duration.setValue(1);w.request((0,3))
        wait(lambda:w.transition is not None and len(m.strips)==2)
        outgoing,incoming=m.bindings();m.set_audio(outgoing,mute=True);assert outgoing.deck.audio.isMuted() and not incoming.deck.config.get('mute')
        wait(lambda:settled(w) and len(m.strips)==1);assert next(iter(m.strips.values())).binding.source is w.lists[0]['items'][3]
        w.effect.setCurrentText('直接切換')
        # Multi-screen: two copies of the same file have independent runtime/source snapshots.
        c=w.compositor;original=copy.deepcopy(w.lists);c.grid(2,2)
        for i,path in enumerate([audio,audio,silent,image]):c.assign_media(c.layers[i],[path])
        wait(lambda:all(not l.pending and not l.transition for l in c.layers) and len(m.strips)==2)
        assert w.lists==original
        first,second=[m.strips[b.key] for b in m.bindings()];a,b=first.binding.deck,second.binding.deck;before=a.player.position();spy=QSignalSpy(a.player.sourceChanged)
        first.slider.setValue(gain_fader(35));QTest.mouseClick(first.mute,Qt.LeftButton)
        assert a.audio.isMuted() and not b.audio.isMuted() and b.config.get('gain',100)==100
        assert c.layers[0].source_items()[0]['mute'] and not c.layers[1].source_items()[0].get('mute')
        wait(lambda:a.player.position()>before+150);assert spy.count()==0 and a.player.playbackState()==QMediaPlayer.PlayingState
        c.list.setCurrentRow(1);assert c.selected() is c.layers[1];c.mute.setChecked(True);assert b.audio.isMuted();m.refresh();m.scroll.ensureWidgetVisible(second);app.processEvents();QTest.mouseClick(second.mute,Qt.LeftButton);assert not b.audio.isMuted() and not c.layers[1].c['mute']
        cue=c.capture_cue('混音');assert cue['layout'][0]['items'][0]['mute'] and abs(cue['layout'][0]['items'][0]['gain']-35)<.3
        for theme in range(4):
            w.interface.apply_theme(theme)
            for layout in range(4):w.interface.apply_layout(layout,save=False);app.processEvents();assert len(m.strips)==2 and first.binding.deck is a
        w.interface.apply_theme(0);w.interface.apply_layout(0,save=False);w.resize(1320,820);app.processEvents()
        for strip in m.strips.values():assert m.scroll.viewport().rect().contains(strip.mute.mapTo(m.scroll.viewport(),strip.mute.rect().center()))
        w.grab().save('/tmp/fader-mixer.png')
        c.scenes=[cue];c.refresh_scenes();c.recall();wait(lambda:all(not l.pending and not l.transition for l in c.layers) and len(m.strips)==2)
        assert c.layers[0].decks[c.layers[0].active].audio.isMuted()
        w.stop();m.refresh();assert not m.strips and m.isHidden();w.close()
print('PASS real audio-track filtering, vertical faders, live/paused mute and gain, unchanged player/source/position, independent identical files, CUE and 16 interface combinations')
