"""單畫面／多畫面 tabs switch the output mode and show the multi-screen panel beside the preview."""
import os,tempfile
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ['MEDIACAROUSEL_SESSION_DIR']=tempfile.mkdtemp()
from unittest.mock import patch
from app import QApplication,Window
from interface import QMessageBox

app=QApplication([]);w=Window();w.session_ready=False;w.session_timer.stop();w.resize(1440,900);w.show();app.processEvents()
ui=w.interface;c=w.compositor
c.enable.setChecked(False);app.processEvents()
assert ui.mode_tabs.currentIndex()==0 and not ui.multi_panel.isVisible()
assert c.tabs.parent() is not None and not c.isVisible()  # the dock itself stays hidden
for i in range(4):ui.apply_layout(i,save=False);assert not c.isVisible(),i  # no layout brings the side dock back
ui.apply_layout(0,save=False)

ui.mode_tabs.setCurrentIndex(1);app.processEvents()
assert c.enabled and c.enable.isChecked() and ui.multi_panel.isVisible()
c.enable.setChecked(False);app.processEvents()
assert ui.mode_tabs.currentIndex()==0 and not ui.multi_panel.isVisible()

# While live and playing, switching asks first; answering No keeps the current mode.
ui._live=True;w.running=True
with patch.object(QMessageBox,'question',return_value=QMessageBox.No):ui.mode_tabs.setCurrentIndex(1)
assert not c.enabled and ui.mode_tabs.currentIndex()==0
with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):ui.mode_tabs.setCurrentIndex(1)
assert c.enabled
w.running=False;ui._live=False
print('PASS: mode tabs switch output, panel beside preview, no side dock in any layout, live confirmation')
w.close();app.processEvents()
