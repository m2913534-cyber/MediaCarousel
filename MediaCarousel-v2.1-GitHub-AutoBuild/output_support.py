"""Output helpers: keep the display awake while live, remember the output screen, GPU viewport."""
import os,subprocess,sys
from PySide6.QtCore import QSettings
from PySide6.QtGui import QGuiApplication

class KeepAwake:
    """Stops the display and system from sleeping while the show is live."""
    def __init__(self):self.process=None;self.active=False
    def set(self,on):
        if on==self.active:return
        self.active=on
        try:
            if sys.platform=='darwin':
                if on:self.process=subprocess.Popen(['/usr/bin/caffeinate','-d','-i','-w',str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                elif self.process:self.process.terminate();self.process=None
            elif sys.platform=='win32':
                import ctypes
                ES_CONTINUOUS,ES_SYSTEM,ES_DISPLAY=0x80000000,0x1,0x2
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS|(ES_SYSTEM|ES_DISPLAY if on else 0))
        except Exception:
            self.process=None
    def close(self):self.set(False)

def preferences():return QSettings('MediaCarousel','Studio')

def remember_screen(screen):
    preferences().setValue('output_screen',screen.name())

def output_screen(fallback):
    """The last chosen screen if still connected, else a secondary screen, else the control screen."""
    screens=QGuiApplication.screens();saved=preferences().value('output_screen','',type=str)
    for s in screens:
        if saved and s.name()==saved:return s
    others=[s for s in screens if s is not fallback]
    return others[0] if others else fallback

def gpu_enabled():
    if QGuiApplication.platformName() in ('offscreen','minimal'):return False
    return preferences().value('output_gpu',True,type=bool)

def set_gpu(view,on):
    """Swap the output view's viewport; overlays read the clean_output flag from the viewport."""
    if on and QGuiApplication.platformName() not in ('offscreen','minimal'):
        from PySide6.QtOpenGLWidgets import QOpenGLWidget
        viewport=QOpenGLWidget()
    else:
        from PySide6.QtWidgets import QWidget
        viewport=QWidget()
    viewport.setProperty('clean_output',True);view.setViewport(viewport);view.refit()
