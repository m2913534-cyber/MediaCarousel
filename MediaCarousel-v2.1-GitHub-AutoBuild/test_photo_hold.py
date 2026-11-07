"""Stills marked hold stay up until advanced manually, in single and multi-screen output."""
import os,time,tempfile,json
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ['MEDIACAROUSEL_SESSION_DIR']=tempfile.mkdtemp()
from pathlib import Path
from PySide6.QtGui import QPixmap,QColor
from app import QApplication,Window
from model import holds,save_project,load_project

assert holds({'path':'a.png','hold':True}) and not holds({'path':'a.png'}) and not holds({'path':'a.mp4','hold':True})
assert holds({'kind':'black','path':'media:black','hold':True})

def pump(seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)

app=QApplication([]);w=Window();w.session_ready=False;w.session_timer.stop()
with tempfile.TemporaryDirectory() as temp:
    paths=[]
    for name in ('red','blue'):
        p=Path(temp)/f'{name}.png';pix=QPixmap(320,180);pix.fill(QColor(name));pix.save(str(p));paths.append(str(p))
    w.lists=[{'name':'hold','items':[{'path':paths[0],'seconds':.5,'hold':True},{'path':paths[1],'seconds':.5}]}]
    w.refresh_groups();w.mode.setCurrentText('清單循環');w.effect.setCurrentText('直接切換');w.duration.setValue(.1)

    # Project files keep the flag; old files without it are left untouched.
    project=Path(temp)/'hold.mcarousel';save_project(project,w.lists,w.settings())
    data=load_project(project);assert data['lists'][0]['items'][0]['hold'] is True and 'hold' not in data['lists'][0]['items'][1]

    # Single screen: held photo stays past its seconds, then advances on demand.
    w.files.setCurrentRow(0);assert w.hold_still.isChecked() and not w.seconds.isEnabled()
    assert '手動' in w.files.item(0).text()
    w.play_selected();pump(1.5);assert w.current==(0,0),w.current
    w.advance();pump(.3);assert w.current==(0,1),w.current
    pump(.8);assert w.current==(0,0),w.current  # unheld photo still auto-advances
    pump(1.0);assert w.current==(0,0),w.current

    # Unticking while it is on screen takes effect immediately.
    w.files.setCurrentRow(0);w.hold_still.setChecked(False);assert not w.lists[0]['items'][0]['hold']
    pump(.8);assert w.current==(0,1),w.current
    w.stop()

    # Multi-screen tile uses the same per-photo flag.
    w.lists[0]['items'][0]['hold']=True
    c=w.compositor;c.restore([{'name':'tile','group':0,'w':640,'h':360}]);c.enable.setChecked(True);c.toggle();pump(1.5)
    l=c.layers[0];assert l.current==(0,0),l.current
    l.advance();pump(.3);assert l.current==(0,1),l.current
    c.toggle();c.enable.setChecked(False)
print('PASS: photo hold in single screen, multi-screen tile, live toggle and project save')
w.close();app.processEvents()
