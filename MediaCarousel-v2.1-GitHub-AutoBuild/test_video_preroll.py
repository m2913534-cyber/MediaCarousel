"""Decode real clips to verify silent, bounded warmup and stale-source fallback."""
import os,tempfile,time,subprocess,copy,hashlib
os.environ['QT_QPA_PLATFORM']='offscreen'
import faulthandler;faulthandler.dump_traceback_later(40,exit=True)
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings,QUrl
from PySide6.QtTest import QSignalSpy
from PySide6.QtMultimedia import QMediaPlayer
from app import Window,Deck
from compositor import MediaDeck
for cls in (Deck,MediaDeck):
    init=cls.__init__
    def headless(self,*a,_init=init,**kw):_init(self,*a,**kw);self.player.setAudioOutput(None)
    cls.__init__=headless
app=QApplication([])
def wait(fn,seconds=8):
    end=time.monotonic()+seconds
    while not fn() and time.monotonic()<end:app.processEvents();time.sleep(.002)
    assert fn(),'timeout'
def settled(w):return not w.pending and not w.transition
with tempfile.TemporaryDirectory() as folder,patch('interface.QSettings',lambda *a:QSettings(folder+'/p.ini',QSettings.IniFormat)):
    paths=[]
    for n,color in enumerate(('red','blue')):
        path=folder+f'/{n}.mp4';subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i',f'color=c={color}:s=160x90:r=25:d=6','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=6','-c:v','libx264','-threads','1','-g','75','-pix_fmt','yuv420p','-c:a','aac','-y',path],check=True);paths.append(path)
    hashes=[hashlib.sha256(open(p,'rb').read()).hexdigest() for p in paths]
    items=[{'path':p,'seconds':60,'start':1.2,'end':4.5,'gain':100,'mute':False} for p in paths]
    w=Window();w.session_ready=False;w.session_timer.stop();w.show();w.effect.setCurrentText('直接切換');w.mode.setCurrentText('清單循環');w.lists=[{'name':'來源','items':items}];w.refresh_groups();w.request((0,0));wait(lambda:settled(w))
    for _ in range(6):
        wait(lambda:w in w.next_cache.jobs and w.decks[w.next_cache.jobs[w]['index']].preroll.ready)
        job=w.next_cache.jobs[w];standby=w.decks[job['index']];old=w.decks[w.active];old_position=old.player.position();wait(lambda:old.player.position()>old_position+80)
        assert standby.player.playbackState()==QMediaPlayer.PausedState and standby.audio.volume()==0
        assert standby.last_frame.startTime()>=1200000 and standby.last_frame.size().width()==160
        spy=QSignalSpy(standby.player.sourceChanged)
        with patch.object(standby.player,'setSource',wraps=standby.player.setSource) as load:
            w.request(job['target']);wait(lambda:settled(w));assert load.call_count==0
        assert w.decks[w.active] is standby and spy.count()==0 and 1200<=standby.player.position()<1600
    # A changed in-point must invalidate the cached clip before it can go live.
    wait(lambda:w in w.next_cache.jobs and w.decks[w.next_cache.jobs[w]['index']].preroll.ready)
    job=w.next_cache.jobs[w];target=job['target'];candidate=items[target[1]];candidate['start']=2.2;w.request(target);wait(lambda:settled(w))
    assert w.decks[w.active].last_frame.startTime()>=2200000
    # Single-file direct loops keep the same player/source and exact clip in-point.
    w.mode.setCurrentText('單檔循環');deck=w.decks[w.active];spy=QSignalSpy(deck.player.sourceChanged);w.advance_media();wait(lambda:deck.player.position()<2500)
    assert w.decks[w.active] is deck and spy.count()==0
    # A corrupt off-air preload must not stop the current video.
    bad=folder+'/broken.mp4';open(bad,'wb').write(b'not a movie');w.mode.setCurrentText('清單循環')
    good=w.current[1];items[1-good]={'path':bad,'seconds':60,'start':0,'end':0};before=deck.player.position();wait(lambda:bool(w.next_cache.cooldown))
    assert w.running and settled(w) and w.decks[w.active] is deck and deck.player.position()>before
    w.stop();w.lists=[{'name':'來源','items':[dict(item) for item in items[:1]]}];w.refresh_groups();c=w.compositor;c.enable.setChecked(True)
    source=[{'path':p,'seconds':60,'start':0,'end':6} for p in paths]
    for i in range(4):
        c.add({'kind':'playlist','group':0,'name':str(i),'x':(i%2)*960,'y':(i//2)*540,'w':960,'h':540,'items':copy.deepcopy(source)});c.layers[-1].request((0,0))
    wait(lambda:all(l.current and not l.pending and not l.transition for l in c.layers))
    for l in c.layers:l.decks[l.active].player.setPosition(4300)
    wait(lambda:len(w.next_cache.jobs)==2 and all(o.decks[j['index']].preroll.ready for o,j in w.next_cache.jobs.items()))
    assert len(w.next_cache.jobs)<=2 and all(o.decks[j['index']].audio.volume()==0 for o,j in w.next_cache.jobs.items())
    assert len(w.lists)==1 and len(w.lists[0]['items'])==1
    w.stop();assert not w.next_cache.jobs
    assert [hashlib.sha256(open(p,'rb').read()).hexdigest() for p in paths]==hashes
    w.close()
faulthandler.cancel_dump_traceback_later()
print('PASS trimmed silent preroll, paused warm first frame, 6 same-source reuse cycles without setSource, changed-in-point fallback, same-player looping, off-air decode failure isolation, two-slot multi cap, no playlist growth, source hashes unchanged')
