"""Media rows: thumbnails for images/PDF/PPT/black, subtitles, and live progress on the playing row."""
import os,time,tempfile
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ['MEDIACAROUSEL_SESSION_DIR']=tempfile.mkdtemp()
from PySide6.QtGui import QPixmap,QColor,QPdfWriter,QPainter,QPageSize
from app import QApplication,Window

def pump(seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)

app=QApplication([]);w=Window();w.session_ready=False;w.session_timer.stop();w.resize(1440,900);w.show()
with tempfile.TemporaryDirectory() as temp:
    img=os.path.join(temp,'wide.png');pix=QPixmap(1600,400);pix.fill(QColor('red'));pix.save(img)
    pdf=os.path.join(temp,'doc.pdf');writer=QPdfWriter(pdf);writer.setPageSize(QPageSize(QPageSize.A6));p=QPainter(writer);p.fillRect(0,0,500,500,QColor('blue'));p.end()
    ppt=os.path.join(temp,'show.pptx');open(ppt,'wb').write(b'x')
    w.compositor.enable.setChecked(False)
    w.lists=[{'name':'t','items':[{'path':img,'seconds':.8},{'path':pdf,'seconds':5},{'path':ppt,'seconds':5},{'kind':'black','path':'media:black','name':'黑畫面','seconds':3,'hold':True},{'path':os.path.join(temp,'gone.png'),'seconds':5}]}]
    w.effect.setCurrentText('直接切換');w.refresh_groups();pump(1.0)
    items=w.lists[0]['items']
    for item in items[:4]:
        thumb=w.thumbnails.get(item);assert thumb is not None and not thumb.isNull(),item['path']
    assert w.thumbnails.get(items[0]).width()==192  # aspect kept, fitted to 192×108
    assert w.thumbnails.get(items[4]) is None        # missing file is not queued
    d=w.files.itemDelegate()
    assert d.subtitle(items[0],False)=='圖片 · 0.8 秒' and d.subtitle(items[3],False)=='黑畫面 · 手動切換' and d.subtitle(items[4],True).startswith('⚠')
    assert d.sizeHint(None.__class__ and type('o',(),{'rect':w.files.rect()})(),None).height()==66

    # Progress grows while the image plays and is None for rows not on air.
    w.files.setCurrentRow(0);w.play_selected();pump(.35);first=w.row_progress(0,0)
    pump(.25);second=w.row_progress(0,0)
    assert first is not None and second is not None and 0<first<second<=1,(first,second);assert w.row_progress(0,2) is None
    w.files.viewport().grab()  # paints every row without errors
    w.stop()
print('PASS: thumbnails (image, PDF, PPT, black), missing file, subtitles, playing-row progress')
w.close();app.processEvents()
