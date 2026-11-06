"""Finish policy persistence and clean transparent removal of an overlapping tile."""
import os,tempfile
os.environ['QT_QPA_PLATFORM']='offscreen'
from unittest.mock import patch
from PySide6.QtCore import QSettings,Qt,QRectF
from PySide6.QtGui import QImage,QColor,QPainter
from PySide6.QtWidgets import QApplication
from app import Window
from model import save_project,load_project
app=QApplication([])
def pixel(w):
    image=QImage(40,40,QImage.Format_RGB32);image.fill(Qt.black);p=QPainter(image);w.screen.scene().render(p,QRectF(0,0,40,40),w.screen.sceneRect());p.end();return image.pixelColor(20,20).name()
with tempfile.TemporaryDirectory() as folder,patch('interface.QSettings',lambda *a:QSettings(folder+'/prefs.ini',QSettings.IniFormat)):
    for name in ('red','blue'):
        image=QImage(100,100,QImage.Format_RGB32);image.fill(QColor(name));image.save(folder+'/'+name+'.png')
    item=lambda color:{'path':folder+'/'+color+'.png','seconds':60,'gain':100,'mute':False}
    w=Window();w.session_ready=False;w.session_timer.stop();w.next_cache.timer.stop();w.effect.setCurrentText('直接切換');w.mode.setCurrentText('播放一次')
    w.lists=[{'name':'來源','items':[item('red')]}];w.refresh_groups()
    for finish in ('hold','hide'):
        w.end_action.setCurrentIndex(w.end_action.findData(finish));w.request((0,0));w.request(None)
        assert pixel(w)==('#ff0000' if finish=='hold' else '#000000')
        assert w.held==(finish=='hold') and not w.running and len(w.lists[0]['items'])==1
        if finish=='hide':assert w.current is None
        w.stop()
    # New explicit values win; old boolean-only sessions and CUEs still migrate.
    for settings,expected in [({'hold_last':False},'hide'),({'hold_last':True},'hold'),({'end_action':'hide','hold_last':True},'hide')]:
        w.apply_settings(settings);assert w.end_action.currentData()==expected
    w.effect.setCurrentText('直接切換');w.mode.setCurrentText('播放一次');w.request((0,0));cue=w.compositor.capture_cue('消失設定');assert cue['settings']['end_action']=='hide'
    project=folder+'/show.mcarousel';save_project(project,w.lists,w.settings(),[cue],[]);assert load_project(project)['settings']['end_action']=='hide'
    w.stop();c=w.compositor;c.enable.setChecked(True);c.edit.setChecked(False)
    for color in ('blue','red'):
        c.add({'name':color,'kind':'playlist','group':0,'x':0,'y':0,'w':1920,'h':1080,'items':[item(color)]});c.layers[-1].request((0,0));c.layers[-1].tick(0)
    bottom,top=c.layers
    assert pixel(w)=='#ff0000'
    w.end_action.setCurrentIndex(0);top.request(None);assert pixel(w)=='#ff0000' and bottom.running
    top.start();top.tick(0);w.end_action.setCurrentIndex(1);top.request(None)
    assert pixel(w)=='#0000ff' and bottom.running and top.brush().style()==Qt.NoBrush
    top.start();top.tick(0);assert pixel(w)=='#ff0000' and top.brush().style()!=Qt.NoBrush
    # Looping continues regardless of the end policy.
    w.mode.setCurrentText('清單循環');top.advance();top.tick(0);assert top.running and not top.held
    w.close()
print('PASS explicit hold/hide, legacy migration, CUE/project persistence, single canvas black, transparent upper tile reveals uninterrupted lower tile, restart and looping')
