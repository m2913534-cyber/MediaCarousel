"""Windows PowerPoint automation. Office objects live only on their COM worker thread."""
import sys,time,queue
from pathlib import Path
from PySide6.QtCore import QThread,Signal

def powerpoint_available():
    if sys.platform!='win32':return False,'PowerPoint 原生整合目前支援 Windows；PDF 可直接播放。'
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,r'PowerPoint.Application\CLSID'):pass
        import pythoncom,win32com.client
        return True,'已偵測 Microsoft PowerPoint 桌面版；播放時會啟動原生放映。'
    except Exception:return False,'未偵測到 Microsoft PowerPoint 桌面版。請先安裝並完成啟用；網頁版不提供此整合。'

def place_window(hwnd,screen_name,index=0):
    import ctypes
    from ctypes import wintypes
    user=ctypes.windll.user32
    class MonitorInfo(ctypes.Structure):
        _fields_=[('cbSize',wintypes.DWORD),('rcMonitor',wintypes.RECT),('rcWork',wintypes.RECT),('dwFlags',wintypes.DWORD),('szDevice',wintypes.WCHAR*32)]
    monitors=[];callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HMONITOR,wintypes.HDC,ctypes.POINTER(wintypes.RECT),wintypes.LPARAM)
    user.GetMonitorInfoW.argtypes=[wintypes.HMONITOR,ctypes.POINTER(MonitorInfo)];user.GetMonitorInfoW.restype=wintypes.BOOL
    def collect(monitor,dc,rect,data):
        info=MonitorInfo();info.cbSize=ctypes.sizeof(info)
        if user.GetMonitorInfoW(monitor,ctypes.byref(info)):monitors.append((info.szDevice,(info.rcMonitor.left,info.rcMonitor.top,info.rcMonitor.right,info.rcMonitor.bottom)))
        return True
    cb=callback(collect);user.EnumDisplayMonitors.argtypes=[wintypes.HDC,ctypes.c_void_p,callback,wintypes.LPARAM];user.EnumDisplayMonitors(None,None,cb,0)
    if not monitors:raise RuntimeError('找不到輸出螢幕')
    rect=next((r for name,r in monitors if name.lower()==screen_name.lower()),monitors[max(0,min(index,len(monitors)-1))][1])
    get_style=getattr(user,'GetWindowLongPtrW',user.GetWindowLongW);set_style=getattr(user,'SetWindowLongPtrW',user.SetWindowLongW)
    get_style.argtypes=[wintypes.HWND,ctypes.c_int];get_style.restype=ctypes.c_ssize_t;set_style.argtypes=[wintypes.HWND,ctypes.c_int,ctypes.c_ssize_t];set_style.restype=ctypes.c_ssize_t
    hwnd=wintypes.HWND(int(hwnd)&0xffffffff);style=get_style(hwnd,-16);set_style(hwnd,-16,(style&~0x00c40000)|0x80000000)
    user.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT];user.SetWindowPos.restype=wintypes.BOOL
    x,y,right,bottom=rect
    if not user.SetWindowPos(hwnd,None,x,y,right-x,bottom-y,0x0060):raise RuntimeError('無法將 PowerPoint 放映視窗移至輸出螢幕')
    user.SetForegroundWindow.argtypes=[wintypes.HWND];user.SetForegroundWindow.restype=wintypes.BOOL;user.SetForegroundWindow(hwnd)

class PowerPointSession:
    """Small testable adapter around documented SlideShowSettings/View members."""
    def __init__(self,app,place=place_window):self.app=app;self.presentation=None;self.window=None;self.place=place
    def start(self,path,screen_name,index=0,slide=1,click=0,timings=False):
        self.close();security=self.app.AutomationSecurity
        try:
            self.app.AutomationSecurity=3
            self.presentation=self.app.Presentations.Open(str(Path(path).resolve()),True,True,False)
        finally:self.app.AutomationSecurity=security
        settings=self.presentation.SlideShowSettings;settings.ShowType=2;settings.ShowWithAnimation=-1;settings.ShowWithNarration=-1;settings.AdvanceMode=2 if timings else 1
        settings.RangeType=1;settings.LoopUntilStopped=0
        self.window=settings.Run();self.place(self.window.HWND,screen_name,index)
        slide=max(1,min(int(slide),int(self.presentation.Slides.Count)))
        if slide>1:self.window.View.GotoSlide(slide,-1)
        if click>0:self.window.View.GotoClick(min(int(click),int(self.window.View.GetClickCount())))
        return self.state()
    def state(self):
        v=self.window.View
        return {'slide':int(v.Slide.SlideIndex),'total':int(self.presentation.Slides.Count),'click':max(0,int(v.GetClickIndex())),'clicks':int(v.GetClickCount()),'state':int(v.State)}
    def command(self,name,value=None):
        v=self.window.View
        if name in ('next','previous'):
            index=max(0,int(v.GetClickIndex()));count=int(v.GetClickCount())
            if name=='next':v.GotoClick(index+1) if index<count else v.Next()
            elif index>0:v.GotoClick(index-1)
            else:v.Previous()
        elif name=='first':v.GotoSlide(1,-1)
        elif name=='last':v.GotoSlide(int(self.presentation.Slides.Count),-1)
        elif name=='goto':v.GotoSlide(max(1,min(int(value),int(self.presentation.Slides.Count))),-1)
        elif name=='pause':v.State=1 if int(v.State)==2 else 2
        elif name=='black':v.State=1 if int(v.State)==3 else 3
        elif name=='move':self.place(self.window.HWND,value['screen_name'],value['index'])
        elif name=='focus':
            import ctypes
            from ctypes import wintypes
            fn=ctypes.windll.user32.SetForegroundWindow;fn.argtypes=[wintypes.HWND];fn.restype=wintypes.BOOL;fn(self.window.HWND)
    def close(self):
        if self.window:
            try:self.window.View.Exit()
            except Exception:pass
        self.window=None
        if self.presentation:
            try:self.presentation.Close()
            except Exception:pass
        self.presentation=None
        # Never quit the application: it may also contain the user's other documents.

class PowerPointWorker(QThread):
    opened=Signal(dict);progress=Signal(dict);ended=Signal(int);failed=Signal(int,str)
    def __init__(self):super().__init__();self.commands=queue.Queue();self.latest_start=None
    def submit(self,name,value=None):
        if name=='start':self.latest_start=value.get('_token',0)
        elif name in ('stop','shutdown'):self.latest_start=None
        self.commands.put((name,value))
        if not self.isRunning():self.start()
    def run(self):
        if sys.platform!='win32':self.failed.emit(0,'PowerPoint 原生整合目前僅支援 Windows');return
        import pythoncom
        pythoncom.CoInitialize();session=None;token=0
        try:
            import win32com.client
            while True:
                try:name,value=self.commands.get(timeout=.1)
                except queue.Empty:name,value=None,None
                if name=='shutdown':break
                try:
                    if name=='start':
                        request=dict(value);token=request.pop('_token',0)
                        if token!=self.latest_start:continue
                        if session:session.close()
                        session=PowerPointSession(win32com.client.DispatchEx('PowerPoint.Application'))
                        state=session.start(**request);state['_token']=token;self.opened.emit(state)
                    elif name=='stop':
                        if session:session.close();session=None
                        self.ended.emit(token)
                    elif name and session:session.command(name,value)
                    pythoncom.PumpWaitingMessages()
                    if session:
                        try:
                            state=session.state()
                            if state['state']==5:raise RuntimeError('放映已結束')
                            state['_token']=token;self.progress.emit(state)
                        except Exception as e:
                            if getattr(e,'hresult',0) in (-2147418111,-2147417846):continue
                            session.close();session=None;self.ended.emit(token)
                except Exception as e:
                    if getattr(e,'hresult',0) in (-2147418111,-2147417846):
                        if name:self.commands.put((name,value))
                        time.sleep(.05);continue
                    if session:session.close();session=None
                    self.failed.emit(token,'PowerPoint 放映失敗：'+str(e)+'；請確認桌面版已啟用，且檔案可在 PowerPoint 正常放映。')
        except Exception as e:self.failed.emit(token,'PowerPoint 整合無法啟動：'+str(e))
        finally:
            if session:session.close()
            pythoncom.CoUninitialize()
    def shutdown(self):
        self.latest_start=None
        if self.isRunning():self.commands.put(('shutdown',None));return self.wait(5000)
        return True
