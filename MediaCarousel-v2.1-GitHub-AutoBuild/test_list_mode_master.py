"""Per-list play mode beside the list, and the MASTER fader driving master volume."""
import os,time,tempfile,json
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ['MEDIACAROUSEL_SESSION_DIR']=tempfile.mkdtemp()
from pathlib import Path
from PySide6.QtGui import QPixmap,QColor
from app import QApplication,Window
from model import following,list_mode,load_project,save_project
from audio_mixer import fader_gain

# Engine: each list follows its own mode; lists without one use the project default.
lists=[{'name':'A','mode':'播完停止','items':[{'path':'a'},{'path':'b'}]},{'name':'B','items':[{'path':'c'}]}]
assert list_mode(lists[0])=='播放一次' and list_mode(lists[1],'所有清單輪播')=='所有清單輪播'
assert following(lists,(0,1),list_mode(lists[0])) is None
lists[0]['mode']='播完接下一清單';assert following(lists,(0,1),list_mode(lists[0]))==(1,0)
lists[0]['mode']='循環';assert following(lists,(0,1),list_mode(lists[0]))==(0,0)

def pump(seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)

app=QApplication([]);w=Window();w.session_ready=False;w.session_timer.stop()
with tempfile.TemporaryDirectory() as temp:
    paths=[]
    for name in ('red','blue'):
        p=os.path.join(temp,name+'.png');pix=QPixmap(160,90);pix.fill(QColor(name));pix.save(p);paths.append(p)
    w.compositor.enable.setChecked(False)
    w.lists=[{'name':'循環清單','items':[{'path':paths[0],'seconds':.4},{'path':paths[1],'seconds':.4}]},{'name':'只播一次','items':[{'path':paths[0],'seconds':.4},{'path':paths[1],'seconds':.4}]}]
    w.mode.setCurrentText('清單循環');w.effect.setCurrentText('直接切換');w.refresh_groups()

    # The combo beside the list edits only that list.
    w.groups.setCurrentIndex(0);assert w.list_mode.currentText()=='循環'
    w.groups.setCurrentIndex(1);w.list_mode.setCurrentText('播完停止')
    assert w.lists[1]['mode']=='播完停止' and 'mode' not in w.lists[0]
    w.groups.setCurrentIndex(0);assert w.list_mode.currentText()=='循環'
    w.groups.setCurrentIndex(1);assert w.list_mode.currentText()=='播完停止'

    # List 1 loops, list 2 stops after its last item.
    w.groups.setCurrentIndex(0);w.files.setCurrentRow(0);w.play_selected();pump(1.5);assert w.running and w.current is not None and w.current[0]==0,w.current
    w.stop();w.groups.setCurrentIndex(1);w.files.setCurrentRow(0);w.play_selected();pump(1.8);assert not w.running,w.current

    # Mode is saved with the list.
    path=Path(temp)/'modes.mcarousel';save_project(path,w.lists,w.settings());data=load_project(path)
    assert data['lists'][1]['mode']=='播完停止' and 'mode' not in data['lists'][0]

    # MASTER fader and the master volume slider stay in sync; MUTE ALL zeroes the level.
    master=w.interface.audio_panel.master;assert master.isVisibleTo(w.interface.audio_panel)
    w.volume.setValue(50);assert abs(fader_gain(master.slider.value())-50)<1
    master.slider.setValue(1000);assert w.volume.value()==100 and w.master_level()==1
    master.mute.setChecked(True);assert w.master_level()==0;master.mute.setChecked(False);assert w.master_level()==1
print('PASS: per-list play mode (loop / stop / next list), saved with project; MASTER fader sync and mute all')
w.close();app.processEvents()
