import os,tempfile,copy
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor,QPainter,QPixmap
from PySide6.QtCore import Qt,QRectF
from PySide6.QtMultimedia import QVideoFrame
from app import Window
app=QApplication([]);w=Window();w.session_ready=False;w.session_timer.stop();c=w.compositor
with tempfile.TemporaryDirectory() as folder:
 im=QImage(400,200,QImage.Format_RGBA8888);p=QPainter(im)
 for rect,color in [(QRectF(0,0,200,100),'red'),(QRectF(200,0,200,100),'green'),(QRectF(0,100,200,100),'blue'),(QRectF(200,100,200,100),'yellow')]:p.fillRect(rect,QColor(color))
 p.end();path=folder+'/corners.png';im.save(path)
 w.lists=[{'name':'來源','items':[{'path':path,'seconds':5,'gain':100,'mute':False}]}];w.refresh_groups();w.files.setCurrentRow(0);original=copy.deepcopy(w.lists)
 c.grid(2,2);c.list.setCurrentRow(0);l=c.selected()
 for _ in range(8):c.use_selected_file();l.tick(1)
 assert w.lists==original and w.groups.count()==1 and w.files.count()==1
 l.setPos(0,0)
 for other in c.layers[1:]:other.hide()
 c.edit.setChecked(False);d=l.decks[l.active]
 for video in [False,True]:
  if video:
   d.image.hide();d.kind='video';d.item=d.video;d.video.videoSink().setVideoFrame(QVideoFrame(im));d.video.setOpacity(1);d.video.show()
  for width,height in [(900,180),(180,900),(650,500),(250,700)]:
   l.resize_to(width,height);app.processEvents()
   if video:assert d.video.aspectRatioMode()==Qt.IgnoreAspectRatio
   else:assert d.image.mapRectToParent(d.image.boundingRect())==QRectF(0,0,width,height)
   out=QImage(width,height,QImage.Format_RGB32);out.fill(Qt.black);p=QPainter(out);w.screen.scene().render(p,QRectF(0,0,width,height),QRectF(0,0,width,height));p.end()
   for x,y,name in [(5,5,'red'),(width-6,5,'green'),(5,height-6,'blue'),(width-6,height-6,'yellow')]:
    a,b=out.pixelColor(x,y),QColor(name)
    assert abs(a.red()-b.red())<10 and abs(a.green()-b.green())<10 and abs(a.blue()-b.blue())<10,(video,width,height,x,y,a.name(),b.name())
 print('PASS complete image/video corners in wide/portrait tiles after repeated resize; no playlist or item growth')
w.close()
