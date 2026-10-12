import os,tempfile,time
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from PySide6.QtGui import QPixmap,QColor
from app import QApplication,Window
from model import EFFECTS
app=QApplication([]);w=Window();w.show()
def pump(n):
    end=time.monotonic()+n
    while time.monotonic()<end:app.processEvents();time.sleep(.005)
with tempfile.TemporaryDirectory() as t:
    paths=[]
    for i,color in enumerate(['red','green']):
        p=Path(t)/f'{i}.png';pix=QPixmap(320,180);pix.fill(QColor(color));pix.save(str(p));paths.append(str(p))
    w.add_files(paths);w.duration.setValue(.1)
    for effect in EFFECTS:
        w.stop();w.files.setCurrentRow(0);w.effect.setCurrentText(effect);w.play_selected();pump(.3);w.advance();pump(.3)
        assert w.current==(0,1) and w.transition is None and w.decks[w.active].item.opacity()==1,effect
    c=w.compositor;c.add_playlist()
    for effect in EFFECTS:
        c.stop();w.effect.setCurrentText(effect);c.toggle();pump(.3);c.advance();pump(.3)
        l=c.layers[0];assert l.current==(0,1) and l.transition is None and l.decks[l.active].item.opacity()==1,effect
    assert w.output_view.scene() is w.screen.scene()
    w.output();pump(.1);assert w.screen.parent() is not None and w.output_view.isVisible();w.output_view.hide()
    print('PASS: all seven single/compositor transition choices and independent output view')
w.close()
