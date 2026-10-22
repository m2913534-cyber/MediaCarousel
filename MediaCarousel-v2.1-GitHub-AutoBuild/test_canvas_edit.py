import os,tempfile
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor
from PySide6.QtCore import Qt,QPoint,QPointF
from PySide6.QtTest import QTest
from app import Window
app=QApplication([]);w=Window();w.session_ready=False;w.session_timer.stop();w.effect.setCurrentText('直接切換')
with tempfile.TemporaryDirectory() as folder:
 path=folder+'/wide.png';im=QImage(1600,200,QImage.Format_RGB32);im.fill(QColor('red'));im.save(path)
 item={'path':path,'seconds':9,'start':2,'end':7,'gain':43,'mute':True}
 w.lists=[{'name':'來源清單','items':[item]}];w.refresh_groups();w.files.setCurrentRow(0);w.show();app.processEvents()
 for width,height in [(1920,1080),(1080,1920)]:
  w.set_canvas(width,height);w.output_fit.setCurrentIndex(1)
  if w.current is None:w.play_selected()
  w.fill_output()
  if not w.single_editor.enabled:w.free_transform()
  app.processEvents();w.screen.refit();app.processEvents()
  assert not w.compositor.enabled and not w.compositor.layers and len(w.lists)==1
  h=w.single_editor.handle;pos=w.screen.mapFromScene(h.mapToScene(QPointF(0,0)))
  start=pos+QPoint(-8,-8);end=start+QPoint(-30,-30)
  QTest.mousePress(w.screen.viewport(),Qt.LeftButton,Qt.NoModifier,start);QTest.mouseMove(w.screen.viewport(),end,100);QTest.mouseRelease(w.screen.viewport(),Qt.LeftButton,Qt.NoModifier,end)
  assert w.decks[w.active].root.scale()<1
  center=w.screen.mapFromScene(w.single_editor.sceneBoundingRect().center())
  QTest.mousePress(w.screen.viewport(),Qt.LeftButton,Qt.NoModifier,center);QTest.mouseMove(w.screen.viewport(),center+QPoint(20,15),100);QTest.mouseRelease(w.screen.viewport(),Qt.LeftButton,Qt.NoModifier,center+QPoint(20,15))
  assert item['single_x']!=0
  w.fill_output();assert item['single_zoom']==1 and item['single_x']==0 and item['single_y']==0
  assert w.decks[w.active].image.sceneBoundingRect()==w.screen.sceneRect()
  w.output_view.resize(960,540);w.output_view.show();w.output_view.refit();app.processEvents();shot=w.output_view.viewport().grab().toImage()
  if height>width:assert shot.pixelColor(10,270).red()==0 and shot.pixelColor(950,270).red()==0
  assert shot.pixelColor(480,270).red()>240
 # Multi-screen stays as tile editing; every resize preserves cover.
 c=w.compositor;c.grid(2,2);c.list.setCurrentRow(0);w.files.setCurrentRow(0);c.use_selected_file();l=c.selected();l.tick(10)
 assert w.lists[l.c['group']]['items'][0]['gain']==43
 l.c['fit']=False;l.resize_to(300,400);assert l.c['fit']
 d=l.decks[l.active];assert d.image.sceneBoundingRect().contains(l.sceneBoundingRect().adjusted(2,2,-2,-2))
 before=len(c.layers);w.free_transform();assert c.enabled and len(c.layers)==before and not w.single_editor.isVisible()
 print('PASS horizontal/portrait single mouse zoom and pan, force stretch reset, no extra tile/list, multi cover')
w.close()
