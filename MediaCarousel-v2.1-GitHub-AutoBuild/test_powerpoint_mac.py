"""Mocked macOS adapter/worker checks. This suite does not run Microsoft Office."""
import tempfile,subprocess,time,unittest,plistlib
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy
from powerpoint_mac import (MacPowerPointSession,DRIVER_SCRIPT,PERMISSION_SCRIPT,
    automation_error,find_powerpoint,AutomationCancelled,AutomationBusy,AutomationInputBlocked,run_process)
from powerpoint import PowerPointWorker,powerpoint_available

class FakeBridge:
    def __init__(self,preexisting=False,fail_after_start=False):
        self.calls=[];self.page=1;self.status=1;self.preexisting=preexisting;self.fail_after_start=fail_after_start;self.busy=False
    def __call__(self,script,args=(),**kwargs):
        if script==PERMISSION_SCRIPT:return 'READY'
        self.calls.append((tuple(args),kwargs));action=args[0]
        if action=='start':
            if self.preexisting:raise RuntimeError('Other show already running')
            Path(args[2]).write_text('owned');Path(args[3]).write_text('PowerPoint Slide Show')
            if self.fail_after_start:raise RuntimeError('Startup interrupted after native show opened')
        elif action=='goto':self.page=int(args[4])
        elif action=='black':self.status=1 if self.status==3 else 3
        elif action=='pause':self.status=1 if self.status==2 else 2
        elif action=='close':self.status=5;return 'ENDED'
        if self.busy:return 'BUSY'
        return f'STATE\n{self.page}\n4\n{self.status}'

class MacAdapterTests(unittest.TestCase):
    def test_native_controls_and_page_restore_without_fake_click_indices(self):
        bridge=FakeBridge();session=MacPowerPointSession(bridge)
        try:
            state=session.start('/tmp/場景 "一".pptx',slide=2,click=3)
            self.assertEqual(state['slide'],2);self.assertIsNone(state['click']);self.assertFalse(state['click_supported'])
            for command in ('next','previous','pause','black','focus'):session.command(command)
            self.assertEqual(session.command('last')['slide'],4);self.assertEqual(session.command('first')['slide'],1)
            self.assertIn('warning',session.command('move',{'index':1}))
            self.assertNotIn('quit',DRIVER_SCRIPT.lower());self.assertNotIn('close presentation',DRIVER_SCRIPT.lower())
            self.assertIn('key code 124',DRIVER_SCRIPT);self.assertIn('key code 123',DRIVER_SCRIPT)
        finally:session.close()
        self.assertEqual(bridge.calls[-1][0][0],'close')
    def test_file_paths_are_argv_not_script_or_shell_source(self):
        bridge=FakeBridge();session=MacPowerPointSession(bridge)
        path='/tmp/動畫 "一"\n$(touch unwanted);.pptx'
        try:
            session.start(path);self.assertEqual(bridge.calls[0][0][1],str(Path(path).resolve()))
            self.assertNotIn(path,DRIVER_SCRIPT)
        finally:session.close()
    def test_preexisting_show_is_never_closed(self):
        bridge=FakeBridge(preexisting=True);session=MacPowerPointSession(bridge)
        with self.assertRaises(RuntimeError):session.start('/tmp/existing.pptx')
        session.close();self.assertEqual([row[0][0] for row in bridge.calls],['start'])
    def test_partial_owned_start_is_cleaned_up_without_closing_documents(self):
        bridge=FakeBridge(fail_after_start=True);session=MacPowerPointSession(bridge)
        with self.assertRaises(RuntimeError):session.start('/tmp/owned.pptx')
        session.close();self.assertEqual([row[0][0] for row in bridge.calls],['start','close'])
        self.assertFalse(bridge.calls[-1][1]['cancelled']())
    def test_busy_state_is_distinct_from_end_of_show(self):
        bridge=FakeBridge();session=MacPowerPointSession(bridge);session.start('/tmp/owned.pptx');bridge.busy=True
        with self.assertRaises(AutomationBusy):session.state()
        self.assertEqual(session.last_state['state'],1);session.close()
    def test_discovery_and_permission_messages(self):
        with tempfile.TemporaryDirectory() as root:
            app=Path(root)/'Applications/Microsoft PowerPoint.app';(app/'Contents').mkdir(parents=True)
            (app/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'com.microsoft.Powerpoint'}))
            with patch('powerpoint_mac.Path.home',return_value=Path(root)),patch('powerpoint_mac.subprocess.run',side_effect=OSError):self.assertEqual(find_powerpoint(),app)
        with patch('powerpoint.sys.platform','darwin'),patch('powerpoint_mac.find_powerpoint',return_value=None):self.assertFalse(powerpoint_available()[0])
        self.assertIn('自動化',automation_error('error (-1743)'));self.assertIn('輔助使用',automation_error('error (-25211)'))
    def test_cancel_terminates_only_the_script_process(self):
        class Process:
            returncode=None;terminated=False
            def poll(self):return self.returncode
            def terminate(self):self.terminated=True;self.returncode=-15
            def communicate(self,**kwargs):return '',''
        process=Process()
        with patch('powerpoint_mac.subprocess.Popen',return_value=process):
            with self.assertRaises(AutomationCancelled):run_process(['/usr/bin/osascript','-'],source='return 1',cancelled=lambda:True)
        self.assertTrue(process.terminated)
    def test_communicate_retry_does_not_resend_input(self):
        class Process:
            returncode=0
            def __init__(self):self.inputs=[]
            def communicate(self,input=None,timeout=None):
                self.inputs.append(input)
                if len(self.inputs)==1:raise subprocess.TimeoutExpired('osascript',timeout)
                return 'READY',''
        process=Process()
        with patch('powerpoint_mac.subprocess.Popen',return_value=process):self.assertEqual(run_process(['osascript'],source='return 1'),'READY')
        self.assertEqual(process.inputs,['return 1',None])

class MacWorkerTests(unittest.TestCase):
    def test_generation_routing_and_busy_command_is_not_replayed(self):
        app=QCoreApplication.instance() or QCoreApplication([]);sessions=[]
        class Session:
            def __init__(self,**kwargs):self.log=[];self.last_state={'slide':1,'total':4,'state':1};sessions.append(self)
            def start(self,**kwargs):return dict(self.last_state)
            def state(self):return dict(self.last_state)
            def command(self,name,value):
                self.log.append(name)
                if name=='next':raise AutomationBusy('busy')
                if name=='focus':raise AutomationInputBlocked('focus is in notes')
                return dict(self.last_state)
            def close(self):self.log.append('close')
        def wait(fn):
            end=time.monotonic()+3
            while not fn() and time.monotonic()<end:app.processEvents();time.sleep(.005)
            self.assertTrue(fn())
        with patch('powerpoint.sys.platform','darwin'),patch('powerpoint_mac.MacPowerPointSession',Session):
            worker=PowerPointWorker();opened=QSignalSpy(worker.opened);failed=QSignalSpy(worker.failed);ended=QSignalSpy(worker.ended)
            try:
                worker.submit('start',{'path':'one.pptx','_token':11});wait(lambda:opened.count()==1)
                worker.submit('next');wait(lambda:sessions[0].log==['next']);time.sleep(.15);app.processEvents()
                self.assertEqual(sessions[0].log,['next']);self.assertEqual(failed.count(),0)
                worker.submit('focus');wait(lambda:'focus' in sessions[0].log);self.assertNotIn('close',sessions[0].log);self.assertEqual(failed.count(),0)
                worker.commands.put(('previous',None,99));worker.submit('start',{'path':'two.pptx','_token':22});wait(lambda:opened.count()==2)
                self.assertNotIn('previous',sessions[0].log);self.assertEqual(opened.at(1)[0]['_token'],22)
                worker.submit('stop');wait(lambda:ended.count()>0);self.assertEqual(failed.count(),0)
            finally:self.assertTrue(worker.shutdown())

if __name__=='__main__':unittest.main()
