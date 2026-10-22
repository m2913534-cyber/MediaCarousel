import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor,QPainter
from PySide6.QtCore import QRectF,Qt
from app import Window
app=QApplication([]);w=Window();w.session_ready=False;w.session_timer.stop()
c=w.compositor;c.grid(2,2);assert len(c.layers)==4
for i,size in enumerate([(200,600),(800,200),(400,400),(1920,1080)]):
    image=QImage(*size,QImage.Format_RGB32);image.fill(QColor('red'));path=f'/tmp/tile{i}.png';image.save(path)
    l=c.layers[i];before=(l.pos(),l.rect());c.assign_media(l,[path]);assert before==(l.pos(),l.rect())
    l.tick(10);d=l.decks[l.active];assert d.image.sceneBoundingRect().contains(l.sceneBoundingRect().adjusted(2,2,-2,-2))
    for mode in ['所有清單輪播','單檔循環','清單循環']:
        w.mode.setCurrentText(mode);assert l.next_target()[0]==l.c['group']
c.list.setCurrentRow(1);before=[(l.pos(),l.rect()) for l in c.layers];c.full_bleed();assert before==[(l.pos(),l.rect()) for l in c.layers]
c.edit.setChecked(False)
image=QImage(1920,1080,QImage.Format_RGB32);image.fill(Qt.black);p=QPainter(image);w.screen.scene().render(p,QRectF(0,0,1920,1080),QRectF(0,0,1920,1080));p.end()
for x in [3,957,963,1917]:
    for y in [3,537,543,1077]:assert image.pixelColor(x,y).red()>240,(x,y,image.pixelColor(x,y).name())
print('PASS: four aspect ratios cover all tile corners; source isolation; tile geometry preserved')
w.close()
