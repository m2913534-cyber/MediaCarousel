import os,tempfile
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor
from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QVideoFrame
from app import Window
from model import save_project,load_project
app=QApplication([]);w=Window();w.session_ready=False;w.session_timer.stop();c=w.compositor
w.set_canvas(3840,2160);c.grid(2,2)
assert c.layers[3].pos().x()==1920 and c.layers[3].pos().y()==1080
assert c.layers[3].rect().width()==1920
image=QImage(200,300,QImage.Format_RGBA8888);image.fill(QColor('red'));image.save('/tmp/hold-test.png')
for l in c.layers:c.assign_media(l,['/tmp/hold-test.png']);l.tick(10)
c.edit.setChecked(True);w.output_view.resize(960,540);w.output_view.show();w.output_view.refit();app.processEvents()
# Clean output must have no label, selection outline, or resize handle even while editing.
snapshot=w.output_view.viewport().grab().toImage()
for y in range(0,snapshot.height(),3):
 for x in range(0,snapshot.width(),3):
  color=snapshot.pixelColor(x,y)
  assert color.red()>240 and color.green()<10,(x,y,color.name())
w.mode.setCurrentText('播放一次');l=c.layers[0];d=l.decks[l.active]
d.kind='video';d.item=d.video;d.last_frame=QVideoFrame(image);d.video.setZValue(2)
l.advance();assert not l.running and d.image.isVisible() and not d.video.isVisible()
assert d.image.pixmap().toImage().pixelColor(10,10).red()==255
with tempfile.TemporaryDirectory() as folder:
 path=folder+'/project.mcarousel';save_project(path,w.lists,w.settings(),[],c.snapshot());data=load_project(path)
 assert data['layout'][3]['x']==1920 and data['settings']['canvas_width']==3840
 w.set_canvas(1920,1080);w.restore_project_data(data)
 assert w.screen.sceneRect().width()==3840 and c.layers[3].pos().x()==1920
w.set_canvas(2160,3840);assert c.layers[3].pos().y()==1920
w.compositor.stop();w.compositor.enable.setChecked(False);w.mode.setCurrentText('播放一次')
w.current=(0,0);d=w.decks[w.active];d.kind='video';d.item=d.video;d.last_frame=QVideoFrame(image);w.request(None)
assert not w.running and d.image.isVisible()
print('PASS: 4K/custom portrait canvas, clean output while editing, held video frame in single/multi, project round trip')
w.close()
