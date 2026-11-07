"""Live output: cursor hidden, keep-awake while on air, LIVE badge, viewport swap keeps overlays clean."""
import os,time,tempfile
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ['MEDIACAROUSEL_SESSION_DIR']=tempfile.mkdtemp()
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap,QColor
from app import QApplication,Window
import output_support

def pump(seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)

calls=[]
class FakeAwake:
    active=False
    def set(self,on):
        if on!=self.active:calls.append(on)
        self.active=on
    def close(self):self.set(False)

app=QApplication([]);w=Window();w.session_ready=False;w.session_timer.stop();w.keep_awake=FakeAwake()
with tempfile.TemporaryDirectory() as temp:
    p=os.path.join(temp,'still.png');pix=QPixmap(320,180);pix.fill(QColor('red'));pix.save(p)
    w.lists=[{'name':'t','items':[{'path':p,'seconds':60}]}];w.refresh_groups();w.compositor.enable.setChecked(False)
    w.refresh_live_state();assert not w.keep_awake.active and '待命' in w.interface.live_label.text()

    # Playing keeps the system awake even before the output goes full screen.
    w.files.setCurrentRow(0);w.play_selected();pump(.5);w.refresh_live_state();assert w.running and w.keep_awake.active
    w.stop();w.refresh_live_state();assert not w.keep_awake.active

    # Full-screen output: LIVE badge, blank cursor, awake; leaving full screen restores all three.
    w.output();pump(.5);w.refresh_live_state()
    v=w.output_view;assert v.isFullScreen()
    assert 'LIVE' in w.interface.live_label.text() and v.viewport().cursor().shape()==Qt.BlankCursor and w.keep_awake.active
    w.output();pump(.3);w.refresh_live_state()
    assert not v.isFullScreen() and '待命' in w.interface.live_label.text() and v.viewport().cursor().shape()==Qt.ArrowCursor and not w.keep_awake.active

    # Swapping the viewport keeps the clean-output flag that hides editing overlays.
    w.set_output_gpu(False);assert v.viewport().property('clean_output')

    # Saved screen is used when connected; unknown names fall back to another screen or the control screen.
    screen=QApplication.primaryScreen()
    with patch.object(output_support,'preferences') as prefs:
        prefs.return_value.value.return_value=screen.name();assert output_support.output_screen(screen) is screen
        prefs.return_value.value.return_value='missing';assert output_support.output_screen(screen) in QApplication.screens()
    v.close()
print('PASS: live badge, hidden cursor, keep-awake on play and output, viewport swap, saved output screen')
w.close();app.processEvents()
