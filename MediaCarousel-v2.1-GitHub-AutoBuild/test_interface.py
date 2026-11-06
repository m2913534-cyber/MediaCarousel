import os,tempfile,copy
os.environ['QT_QPA_PLATFORM']='offscreen'
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor
from PySide6.QtCore import QSettings
from app import Window
app=QApplication([])
with tempfile.TemporaryDirectory() as folder:
 prefs=folder+'/interface.ini'
 with patch('interface.QSettings',lambda *args:QSettings(prefs,QSettings.IniFormat)):
  w=Window();w.session_ready=False;w.session_timer.stop();w.show();app.processEvents();w.effect.setCurrentText('直接切換')
  image=QImage(300,600,QImage.Format_RGB32);image.fill(QColor('red'));path=folder+'/portrait.png';image.save(path)
  w.lists=[{'name':'來源','items':[{'path':path,'seconds':300,'gain':100,'mute':False,'single_zoom':.8,'single_x':.1}]}];w.refresh_groups();w.files.setCurrentRow(0);w.play_selected()
  c=w.compositor;c.scenes=[c.capture_cue('開場'),c.capture_cue('第二段')];c.refresh_scenes();c.scene_list.setCurrentIndex(1)
  current=w.current;deck=w.decks[w.active];screen=w.screen;cue=copy.deepcopy(c.scenes);data=copy.deepcopy(w.lists)
  for theme in range(4):
   for layout in range(4):
    w.interface.apply_theme(theme);w.interface.apply_layout(layout);app.processEvents()
    assert w.interface.theme_combo.currentIndex()==theme and w.interface.layout_combo.currentIndex()==layout
    assert w.screen is screen and w.decks[w.active] is deck and w.current==current and w.running
    assert c.scenes==cue and w.lists==data and c.scene_list.currentIndex()==1
    assert w.screen.width()>170 and w.screen.height()>99
    assert w.interface.audio_dock.isVisible()
    if layout==3:assert w.interface.audio_dock not in w.tabifiedDockWidgets(w.interface.asset_dock)
  # Keyboard/view selection must drive the same CUE source used by GO.
  w.interface.cue_panel.view.setCurrentIndex(c.scene_list.model().index(0,0));assert c.scene_list.currentIndex()==0
  # Style/layout changes are operator preferences; recalling a CUE must not change them.
  w.interface.apply_theme(1);w.interface.apply_layout(2);c.recall();assert w.interface.theme_index==1 and w.interface.layout_index==2
  # Switching a live multi-screen session preserves decks and layer geometry too.
  c.grid(2,2);w.files.setCurrentRow(0);c.use_selected_file();l=c.selected();l.tick(1);saved=c.snapshot();player=l.decks[l.active].player
  for layout in range(4):
   w.interface.apply_layout(layout,save=False);app.processEvents();assert c.snapshot()==saved and l.running and l.decks[l.active].player is player
  w.close()
  restored=Window();restored.session_ready=False;restored.session_timer.stop()
  assert restored.interface.theme_index==1 and restored.interface.layout_index==2
  restored.close()
print('PASS 16 combinations, same playback objects/contents/CUE selection, keyboard CUE selection, independent operator preferences, restart restore')
