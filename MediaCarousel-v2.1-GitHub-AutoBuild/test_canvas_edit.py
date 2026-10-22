import os,tempfile
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor
from PySide6.QtCore import Qt,QPointF
from PySide6.QtTest import QTest
from app import Window
app=QApplication([]);w=Window();w.session_ready=False;w.session_timer.stop()
with tempfile.TemporaryDirectory() as folder:
 path=folder+'/wide.png';im=QImage(1600,200,QImage.Format_RGB32);im.fill(QColor('red'));im.save(path)
 item={'path':path,'seconds':9,'start':2,'end':7,'gain':43,'mute':True}
 w.lists=[{'name':'來源清單','items':[item]}];w.refresh_groups();w.files.setCurrentRow(0)
 w.set_canvas(1080,1920);w.output_fit.setCurrentIndex(1);w.fit.setCurrentIndex(1);w.effect.setCurrentText('直接切換');w.request((0,0))
 w.output_view.resize(960,540);w.output_view.show();w.output_view.refit();app.processEvents()
 shot=w.output_view.viewport().grab().toImage()
 assert shot.pixelColor(10,270).red()==0 and shot.pixelColor(950,270).red()==0
 assert shot.pixelColor(480,10).red()>240 and shot.pixelColor(480,530).red()>240
 w.free_transform();c=w.compositor;l=c.selected();l.tick(10)
 assert w.lists[l.c['group']]['items'][0]==item
 assert w.group_index()==0 and w.files.currentRow()==0
 w.show();app.processEvents();w.screen.refit();app.processEvents()
 before=l.c['w'];handle=l.handle
 pos=w.screen.mapFromScene(handle.mapToScene(QPointF(0,0)))
 # Handle occupies a fixed 18 px area inward from the corner at any canvas scale.
 start=pos+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(-8,-8)
 end=start+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(-30,-40)
 QTest.mousePress(w.screen.viewport(),Qt.LeftButton,Qt.NoModifier,start);QTest.mouseMove(w.screen.viewport(),end,100);QTest.mouseRelease(w.screen.viewport(),Qt.LeftButton,Qt.NoModifier,end)
 assert l.c['w']<before,(before,l.c['w'])
 assert l.c['h']<1920
 print('PASS: portrait clipping, complete output, source selection preserves edits, actual mouse resize')
w.close()
