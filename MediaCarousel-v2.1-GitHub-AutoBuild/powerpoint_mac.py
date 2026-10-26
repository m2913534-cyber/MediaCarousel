"""macOS PowerPoint native playback through AppleScript and scoped native keys.

No document export, macro-security changes, app quit or document-close commands.
PowerPoint renders its own animations/media. CUE animation click indices are not
invented where the Mac scripting interface cannot report them.
"""
import hashlib,plistlib,subprocess,tempfile,time
from pathlib import Path

BUNDLE_ID='com.microsoft.Powerpoint'

class AutomationCancelled(RuntimeError):pass
class AutomationBusy(RuntimeError):pass
class AutomationInputBlocked(RuntimeError):pass

def find_powerpoint():
    candidates=[Path('/Applications/Microsoft PowerPoint.app'),Path.home()/'Applications/Microsoft PowerPoint.app']
    try:
        result=subprocess.run(['/usr/bin/mdfind',"kMDItemCFBundleIdentifier == 'com.microsoft.Powerpoint'"],capture_output=True,text=True,timeout=3)
        candidates.extend(Path(line) for line in result.stdout.splitlines() if line)
    except (OSError,subprocess.TimeoutExpired):pass
    for path in candidates:
        try:
            info=plistlib.loads((path/'Contents/Info.plist').read_bytes())
            if str(info.get('CFBundleIdentifier','')).lower()==BUNDLE_ID.lower():return path
        except (OSError,plistlib.InvalidFileException,ValueError):pass
    return None

def mac_powerpoint_available():
    if not find_powerpoint():return False,'未偵測到 Mac 桌面版 Microsoft PowerPoint。請先安裝並完成啟用；網頁版不支援原生動畫整合。'
    return True,'已偵測 Mac PowerPoint；可原生播放 PPT 動畫與音效。首次使用需允許「自動化」及「輔助使用」。'

def automation_error(message):
    if '-1743' in message or 'not authorized' in message.lower():
        return 'macOS 未允許自動化控制。請到系統設定 → 隱私權與安全性 → 自動化，允許 MediaCarousel 控制 Microsoft PowerPoint 與 System Events。'
    if any(value in message.lower() for value in ('-1719','-25211','-10004','assistive','accessibility','輔助','辅助')):
        return 'macOS 未允許輔助使用。請到系統設定 → 隱私權與安全性 → 輔助使用，允許 MediaCarousel，然後重新播放。'
    return 'Mac PowerPoint 控制失敗：'+message.strip()[:450]

def run_process(argv,source=None,cancelled=lambda:False,timeout=30):
    process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    deadline=time.monotonic()+timeout;first=True
    try:
        while True:
            if cancelled():raise AutomationCancelled('已取消 PowerPoint 操作')
            if time.monotonic()>deadline:raise TimeoutError('PowerPoint 回應逾時；請先完成 Office 啟用、檔案提示與 macOS 權限設定。')
            try:
                out,err=process.communicate(input=source if first else None,timeout=.1)
                if process.returncode:
                    if '-1712' in err:raise AutomationBusy('PowerPoint 忙碌中，請稍候；不會重送動畫按鍵。')
                    if '-27002' in err or '-10006' in err:raise AutomationInputBlocked(automation_error(err))
                    raise RuntimeError(automation_error(err))
                return out.strip()
            except subprocess.TimeoutExpired:first=False
    except BaseException:
        if process.poll() is None:
            process.terminate()
            try:process.communicate(timeout=1)
            except subprocess.TimeoutExpired:process.kill();process.communicate()
        raise

class CompiledScripts:
    """Compile the installed app's dictionary once, off the Qt GUI thread."""
    def __init__(self):self.temp=tempfile.TemporaryDirectory(prefix='MediaCarousel-AppleScript-')
    def compile(self,script,cancelled=lambda:False,timeout=30):
        path=Path(self.temp.name)/(hashlib.sha256(script.encode()).hexdigest()+'.scpt')
        if not path.exists():run_process(['/usr/bin/osacompile','-o',str(path),'-'],script,cancelled,timeout)
        return path
    def __call__(self,script,args=(),cancelled=lambda:False,timeout=30):
        path=self.compile(script,cancelled,timeout)
        return run_process(['/usr/bin/osascript',str(path),*map(str,args)],cancelled=cancelled,timeout=timeout)
    def close(self):self.temp.cleanup()

def verify_mac_bridge():
    """Compile only OS terms on CI; this does not authorize or run Office."""
    if not all(Path(p).is_file() for p in ('/usr/bin/osascript','/usr/bin/osacompile')):return False
    scripts=CompiledScripts()
    try:return scripts.compile(PERMISSION_SCRIPT).is_file()
    finally:scripts.close()

PERMISSION_SCRIPT='''
tell application "System Events"
    if UI elements enabled is false then error "Accessibility permission required (-25211)"
end tell
return "READY"
'''

DRIVER_SCRIPT=r'''
on writeMarker(filePath, valueText)
    set handle to open for access POSIX file filePath with write permission
    try
        set eof of handle to 0
        write valueText to handle as «class utf8»
        close access handle
    on error messageText number errorNumber
        close access handle
        error messageText number errorNumber
    end try
end writeMarker

on readMarker(filePath)
    try
        return read POSIX file filePath as «class utf8»
    on error
        return ""
    end try
end readMarker

on ownedPresentation(expectedPath)
    tell application id "com.microsoft.Powerpoint"
        repeat with doc in presentations
            set docPath to full name of doc as text
            try
                set docPath to POSIX path of (docPath as alias)
            end try
            if docPath is expectedPath then return contents of doc
        end repeat
    end tell
    return missing value
end ownedPresentation

on showState(expectedPath)
    tell application id "com.microsoft.Powerpoint"
        set doc to my ownedPresentation(expectedPath)
        if doc is missing value then return "ENDED"
        if not (exists slide show window of doc) then return "ENDED"
        try
            set nativeView to slide show view of slide show window of doc
            set pageIndex to slide index of slide of nativeView
            set pageCount to count of slides of doc
            set nativeState to slide state of nativeView
        on error
            return "BUSY"
        end try
        set stateCode to 1
        if nativeState is slide show state paused then set stateCode to 2
        if nativeState is slide show state black screen then set stateCode to 3
        return "STATE" & linefeed & pageIndex & linefeed & pageCount & linefeed & stateCode
    end tell
end showState

on focusOwned(expectedPath, titleFile)
    tell application id "com.microsoft.Powerpoint"
        set doc to my ownedPresentation(expectedPath)
        if doc is missing value then error "The managed presentation is no longer open"
        if not (exists slide show window of doc) then error "The managed slide show has ended"
        if (count of slide show windows) is not 1 then error "請先結束其他 PowerPoint 放映，再使用本程式控制。" number -27002
        activate
    end tell
    set expectedTitle to my readMarker(titleFile)
    if expectedTitle is "" then error "放映視窗未就緒；請重新從 MediaCarousel 播放。" number -27002
    tell application "System Events"
        tell process "Microsoft PowerPoint"
            set frontmost to true
            set targets to windows whose name is expectedTitle
            if (count of targets) is not 1 then error "找不到本程式啟動的放映視窗；請重新播放。" number -27002
            perform action "AXRaise" of item 1 of targets
            if frontmost is false then error "PowerPoint 未取得控制焦點，已取消按鍵。" number -27002
        end tell
    end tell
end focusOwned

on checkKeyboardFocus()
    tell application "System Events"
        tell process "Microsoft PowerPoint"
            try
                set activeElement to value of attribute "AXFocusedUIElement"
                set activeRole to role of activeElement
            on error
                error "無法確認 PowerPoint 按鍵焦點；請先點一下放映畫面再試。" number -27002
            end try
            if activeRole is in {"AXTextField", "AXTextArea", "AXComboBox"} then error "PowerPoint 焦點在文字輸入欄位；請先點一下放映畫面，避免把簡報指令輸入筆記。" number -27002
        end tell
    end tell
end checkKeyboardFocus

on run argv
    set operation to item 1 of argv
    set expectedPath to item 2 of argv
    set ownerFile to item 3 of argv
    set titleFile to item 4 of argv
    set pageValue to item 5 of argv as integer
    if operation is not "start" then
        if application id "com.microsoft.Powerpoint" is not running then return "ENDED"
    end if
    if operation is "start" then
        tell application id "com.microsoft.Powerpoint"
            if (count of slide show windows) > 0 then error "PowerPoint 已在放映；請先自行結束既有放映，本程式不會中斷其他簡報。"
            open POSIX file expectedPath
            set doc to my ownedPresentation(expectedPath)
            if doc is missing value then error "無法確認 PowerPoint 已開啟指定檔案。"
            if not (exists slide show window of doc) then run slide show slide show settings of doc
            my writeMarker(ownerFile, "owned")
            activate
        end tell
        delay 0.5
        tell application "System Events"
            tell process "Microsoft PowerPoint"
                set frontmost to true
                if (count of windows) is 0 then error "PowerPoint 放映視窗尚未出現。"
                my writeMarker(titleFile, name of front window as text)
            end tell
        end tell
    else if operation is "close" then
        if my readMarker(ownerFile) is not "owned" then return "ENDED"
        tell application id "com.microsoft.Powerpoint"
            set doc to my ownedPresentation(expectedPath)
            if doc is not missing value then
                if exists slide show window of doc then exit slide show slide show view of slide show window of doc
            end if
        end tell
        return "ENDED"
    else if operation is "state" then
        return my showState(expectedPath)
    else
        my focusOwned(expectedPath, titleFile)
        if operation is "next" or operation is "previous" then
            my checkKeyboardFocus()
            tell application "System Events" to tell process "Microsoft PowerPoint"
                if operation is "next" then
                    key code 124
                else
                    key code 123
                end if
            end tell
        else if operation is "goto" then
            my checkKeyboardFocus()
            tell application "System Events" to tell process "Microsoft PowerPoint"
                keystroke (pageValue as text)
                key code 36
            end tell
        else if operation is "pause" or operation is "black" then
            tell application id "com.microsoft.Powerpoint"
                set doc to my ownedPresentation(expectedPath)
                set nativeView to slide show view of slide show window of doc
                if operation is "pause" then
                    if slide state of nativeView is slide show state paused then
                        set slide state of nativeView to slide show state running
                    else
                        set slide state of nativeView to slide show state paused
                    end if
                else
                    if slide state of nativeView is slide show state black screen then
                        set slide state of nativeView to slide show state running
                    else
                        set slide state of nativeView to slide show state black screen
                    end if
                end if
            end tell
        else if operation is not "focus" then
            error "Unsupported PowerPoint command"
        end if
    end if
    return my showState(expectedPath)
end run
'''

class MacPowerPointSession:
    def __init__(self,runner=None,cancelled=lambda:False):
        self.runner=runner;self.owns_runner=runner is None;self.cancelled=cancelled;self.path=None;self.temp=None;self.last_state={'slide':1,'total':1,'state':5}
    def call(self,operation,value=0,cleanup=False):
        result=self.runner(DRIVER_SCRIPT,[operation,self.path,self.owner_file,self.title_file,int(value)],cancelled=(lambda:False) if cleanup else self.cancelled,timeout=5 if cleanup else 30)
        if result=='BUSY':raise AutomationBusy('PowerPoint 動畫或換頁正在處理中，請稍候。')
        if result=='ENDED':state=dict(self.last_state,state=5)
        else:
            lines=result.splitlines()
            if len(lines)!=4 or lines[0]!='STATE':raise RuntimeError('PowerPoint 回傳格式不正確')
            slide,total,status=map(int,lines[1:]);state={'slide':max(1,slide),'total':max(1,total),'state':status}
        state.update(click=None,clicks=None,click_supported=False,manual_output=True,timings_native=True)
        self.last_state=state;return dict(state)
    def start(self,path,screen_name='',index=0,slide=1,click=0,timings=False):
        self.close()
        if self.runner is None:self.runner=CompiledScripts()
        self.runner(PERMISSION_SCRIPT,cancelled=self.cancelled,timeout=30)
        self.path=str(Path(path).resolve());self.temp=tempfile.TemporaryDirectory(prefix='MediaCarousel-PowerPoint-')
        self.owner_file=str(Path(self.temp.name)/'owned');self.title_file=str(Path(self.temp.name)/'window-title')
        try:state=self.call('start')
        except AutomationBusy:
            deadline=time.monotonic()+5
            while True:
                try:state=self.state();break
                except AutomationBusy:
                    if time.monotonic()>=deadline:raise
                    time.sleep(.1)
        if state['state']==5:raise RuntimeError('PowerPoint 未進入放映；請先完成 Office 啟用及檔案提示。')
        if int(slide)>1:
            wanted=min(int(slide),state['total']);self.command('goto',wanted);state=self.state();deadline=time.monotonic()+3
            while state['slide']!=wanted and time.monotonic()<deadline:time.sleep(.1);state=self.state()
            if state['slide']!=wanted:raise RuntimeError('PowerPoint 未切換至指定的 CUE 頁碼，請重新播放並確認簡報視窗可接收按鍵。')
        state['warning']='Mac 原生動畫與音效已交由 PowerPoint 播放；輸出螢幕、原有換頁時間請在 PowerPoint 設定。CUE 還原頁碼，動畫步驟由 PowerPoint 控制。'
        return state
    def state(self):return self.call('state') if self.path else dict(self.last_state,state=5)
    def command(self,name,value=None):
        if name in ('first','last'):return self.call('goto',1 if name=='first' else self.state()['total'])
        if name=='goto':return self.call('goto',max(1,min(int(value),self.state()['total'])))
        if name=='move':return dict(self.last_state,warning='Mac PPT 的輸出螢幕請在 PowerPoint 的投影片放映／監視器設定。')
        if name not in ('next','previous','pause','black','focus'):raise ValueError('Unknown PowerPoint command')
        return self.call(name)
    def close(self):
        try:
            if self.path and Path(self.owner_file).is_file():self.call('close',cleanup=True)
        except Exception:pass
        finally:
            self.path=None
            if self.temp:self.temp.cleanup();self.temp=None
            if self.owns_runner and self.runner:self.runner.close();self.runner=None
