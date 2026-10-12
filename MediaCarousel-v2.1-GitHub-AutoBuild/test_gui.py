"""Headless native Qt smoke test; no hardware capture claimed."""
import os,sys,time,tempfile
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from PySide6.QtGui import QPixmap,QColor
from app import QApplication,Window
from model import save_project,load_project

def pump(seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)

app=QApplication([]);w=Window();w.show()
with tempfile.TemporaryDirectory() as temp:
    p=Path(temp)/'red.png';pix=QPixmap(320,180);pix.fill(QColor('red'));pix.save(str(p))
    w.add_files([str(p)]);w.duration.setValue(.1);w.play_selected();pump(.3)
    assert w.current==(0,0) and w.decks[w.active].item.opacity()==1
    w.toggle();assert not w.running;w.toggle();assert w.running;w.stop()
    c=w.compositor
    for i in range(12):c.add_playlist()
    assert len(c.layers)==12 and c.enabled
    c.grid(4,3);assert c.layers[11].pos().x()==1440 and c.layers[11].pos().y()==720
    c.edit.setChecked(False);assert not any(l.handle.isVisible() for l in c.layers)
    c.toggle();pump(.5);assert all(l.current==(0,0) and l.decks[l.active].item.opacity()==1 for l in c.layers)
    c.toggle();assert not any(l.running for l in c.layers)
    layout=c.snapshot();path=Path(temp)/'test.mcarousel';save_project(path,w.lists,w.settings(),[{'name':'12-grid','layout':layout}],layout)
    data=load_project(path);c.restore(data['layout']);assert len(c.layers)==12 and not any(l.running for l in c.layers)
    c.list.setCurrentRow(0);c.controls['w'].setValue(777);assert c.layers[0].c['w']==777
    c.restore(layout);
    if os.environ.get('MEDIA_TEST_SCREENSHOT'):w.grab().save(os.environ['MEDIA_TEST_SCREENSHOT'])
    print('PASS: single image, pause/resume, 12 independent image decks, grid, edit mode, scene roundtrip, geometry controls')
    c.stop();c.enable.setChecked(False)
    clip=Path(os.environ.get('MEDIA_TEST_CLIP','test-clip.mp4'))
    if clip.exists():
        w.lists=[{'name':'clip','items':[{'path':str(clip),'seconds':5,'start':1,'end':2,'gain':30,'mute':False}]}];w.refresh_groups();w.mode.setCurrentText('播放一次');w.effect.setCurrentText('直接切換');w.play_selected();pump(.55)
        d=w.decks[w.active];assert w.current==(0,0),w.status.text();assert 1000<=d.player.position()<=2100,d.player.position()
        pump(1.5);assert w.current is None,w.status.text()
        print('PASS: native FFmpeg MP4 decoding, trim start, trim stop / play once')
        c.restore([{'name':'clip','group':0,'w':640,'h':360}]);c.enable.setChecked(True);c.toggle();pump(.5)
        l=c.layers[0];assert l.current==(0,0),w.status.text();assert 1000<=l.decks[l.active].player.position()<=2100
        pump(1.5);assert l.current is None
        print('PASS: compositor video decoding and trimmed play-once')
w.close();app.processEvents()
