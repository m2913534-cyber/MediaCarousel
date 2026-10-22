import os,tempfile
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor
from PySide6.QtCore import Qt,QPoint,QPointF
from PySide6.QtTest import QTest
from app import Window
from model import save_project,load_project,single_transform
app=QApplication([]);w=Window();w.session_ready=False;w.session_timer.stop();w.effect.setCurrentText('直接切換')
with tempfile.TemporaryDirectory() as folder:
 path=folder+'/wide.png';im=QImage(1600,200,QImage.Format_RGB32);im.fill(QColor('red'));im.save(path)
 item={'path':path,'seconds':9,'start':2,'end':7,'gain':43,'mute':True}
 w.lists=[{'name':'來源清單','items':[item]}];w.refresh_groups();w.files.setCurrentRow(0);w.show();app.processEvents()
 for width,height in [(1920,1080),(1080,1920)]:
  w.set_canvas(width,height);w.output_fit.setCurrentIndex(1)
  if w.current is None:w.play_selected()
  if not w.single_editor.enabled:w.free_transform()
  app.processEvents();w.screen.refit();app.processEvents()
  assert not w.compositor.enabled and not w.compositor.layers and len(w.lists)==1
  editor=w.single_editor;deck=w.decks[w.active]
  assert editor.mapRectToScene(editor.rect())==deck.item.sceneBoundingRect()
  for (horizontal,vertical),handle in editor.handles.items():
   w.fill_output();app.processEvents();before=deck.item.sceneBoundingRect()
   center=handle.rect().center();start=w.screen.mapFromScene(handle.scenePos())+QPoint(round(center.x()),round(center.y()))
   end=start+QPoint(-horizontal*30,-vertical*18)
   QTest.mousePress(w.screen.viewport(),Qt.LeftButton,Qt.NoModifier,start);QTest.mouseMove(w.screen.viewport(),end,20);QTest.mouseRelease(w.screen.viewport(),Qt.LeftButton,Qt.NoModifier,end)
   after=deck.item.sceneBoundingRect();x,y,sx,sy=editor.values()
   if horizontal:
    assert after.width()<before.width(),(width,height,horizontal,vertical,before,after)
    assert abs((after.right() if horizontal<0 else after.left())-(before.right() if horizontal<0 else before.left()))<1e-6
   else:assert abs(after.width()-before.width())<1e-6 and sx==1
   if vertical:
    assert after.height()<before.height()
    assert abs((after.bottom() if vertical<0 else after.top())-(before.bottom() if vertical<0 else before.top()))<1e-6
   else:assert abs(after.height()-before.height())<1e-6 and sy==1
   assert abs(sx-sy)>1e-4
  center=w.screen.mapFromScene(w.single_editor.sceneBoundingRect().center())
  QTest.mousePress(w.screen.viewport(),Qt.LeftButton,Qt.NoModifier,center);QTest.mouseMove(w.screen.viewport(),center+QPoint(20,15),100);QTest.mouseRelease(w.screen.viewport(),Qt.LeftButton,Qt.NoModifier,center+QPoint(20,15))
  assert item['single_x']!=0
  w.fill_output();assert item['single_scale_x']==item['single_scale_y']==1 and item['single_x']==0 and item['single_y']==0
  assert w.decks[w.active].image.sceneBoundingRect()==w.screen.sceneRect()
  w.output_view.resize(960,540);w.output_view.show();w.output_view.refit();app.processEvents();shot=w.output_view.viewport().grab().toImage()
  if height>width:assert shot.pixelColor(10,270).red()==0 and shot.pixelColor(950,270).red()==0
  assert shot.pixelColor(480,270).red()>240
  for handle in editor.handles.values():
   center=handle.rect().center();point=w.output_view.mapFromScene(handle.scenePos())+QPoint(round(center.x()),round(center.y()))
   color=shot.pixelColor(point);assert color.red()>240 and color.green()<10
 # Unequal dimensions survive CUE recall and project persistence; old zooms migrate.
 editor.apply(.1,.2,.6,.85);cue=w.compositor.capture_cue('自由寬高');w.compositor.scenes=[cue];w.compositor.refresh_scenes()
 editor.apply(.3,.1,.8,.4);w.compositor.recall();assert editor.values()==(.1,.2,.6,.85)
 project=folder+'/resize.mcarousel';save_project(project,w.lists,w.settings(),w.compositor.scenes,w.compositor.snapshot());saved=load_project(project)
 assert single_transform(saved['scenes'][0]['single']['media'])==(.1,.2,.6,.85)
 assert single_transform({'single_zoom':.75})==(0,0,.75,.75)
 assert single_transform({'single_zoom':.75,'single_scale_x':.5})==(0,0,.5,.75)
 # Multi-screen stays as tile editing; every resize preserves cover.
 c=w.compositor;c.grid(2,2);c.list.setCurrentRow(0);w.files.setCurrentRow(0);c.use_selected_file();l=c.selected();l.tick(10)
 assert w.lists[l.c['group']]['items'][0]['gain']==43
 l.c['fit']=False;l.resize_to(300,400);assert l.c['fit']
 d=l.decks[l.active];assert d.image.sceneBoundingRect().contains(l.sceneBoundingRect().adjusted(2,2,-2,-2))
 before=len(c.layers);w.free_transform();assert c.enabled and len(c.layers)==before and not w.single_editor.isVisible()
 print('PASS eight independent edge/corner handles in horizontal/portrait canvas, opposite edge anchors, media bounds, pan, CUE/project dimensions, legacy zoom, reset and multi cover')
w.close()
