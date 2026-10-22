import os,tempfile,time,copy
os.environ['QT_QPA_PLATFORM']='offscreen'
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QLineEdit
from PySide6.QtCore import Qt,QMarginsF,QSize
from PySide6.QtGui import QPdfWriter,QPainter,QColor
from PySide6.QtTest import QTest
from app import Window
from model import save_project,load_project
from powerpoint import PowerPointSession
app=QApplication([])
def wait(fn):
 deadline=time.monotonic()+10
 while not fn() and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
 assert fn()
with tempfile.TemporaryDirectory() as folder:
 path=folder+'/pages.pdf';writer=QPdfWriter(path);writer.setPageMargins(QMarginsF(0,0,0,0));p=QPainter(writer)
 for i,color in enumerate(['red','green','blue']):
  if i:writer.newPage()
  p.fillRect(0,0,writer.width(),writer.height(),QColor(color))
 p.end();del writer
 w=Window();w.session_ready=False;w.session_timer.stop();w.show();w.activateWindow();app.processEvents();w.effect.setCurrentText('直接切換');w.mode.setCurrentText('播放一次')
 w.lists=[{'name':'簡報','items':[{'path':path,'seconds':.5,'start':0,'end':0,'gain':100,'mute':False}]}];w.refresh_groups();w.files.setCurrentRow(0);w.play_selected()
 wait(lambda:not w.pending and not w.transition and w.decks[w.active].kind=='pdf' and not w.decks[w.active].pdf_source.loading)
 d=w.decks[w.active];assert d.pdf_source.count==3 and d.image.pixmap().toImage().pixelColor(100,100).red()>240
 w.screen.setFocus();QTest.keyClick(w.screen,Qt.Key_PageDown);wait(lambda:w.current_item().get('pdf_page')==1)
 assert d.image.pixmap().toImage().pixelColor(100,100).green()>100
 QTest.keyClick(w.screen,Qt.Key_Space);wait(lambda:w.current_item().get('pdf_page')==2)
 QTest.keyClick(w.screen,Qt.Key_PageUp);wait(lambda:w.current_item().get('pdf_page')==1)
 cue=w.compositor.capture_cue('PDF 第二頁');assert cue['single']['media']['pdf_page']==1
 QTest.keyClick(w.screen,Qt.Key_B);assert w.presentations.overlay.isVisible();QTest.keyClick(w.screen,Qt.Key_B);assert not w.presentations.overlay.isVisible()
 # Keyboard input in editable fields is not stolen by presenter routing.
 edit=QLineEdit(w);edit.show();edit.setFocus();QTest.keyClicks(edit,'b');assert edit.text()=='b' and not w.presentations.black;edit.close();w.screen.setFocus()
 w.presentations.pen.setChecked(False);before=d.pdf_source.page;QTest.keyClick(w.screen,Qt.Key_PageDown);assert d.pdf_source.page==before;w.presentations.pen.setChecked(True)
 w.compositor.scenes=[cue];w.compositor.refresh_scenes();w.stop();w.compositor.recall();wait(lambda:not w.pending and not w.transition and w.decks[w.active].config.get('pdf_page')==1)
 project=folder+'/show.mcarousel';save_project(project,w.lists,w.settings(),w.compositor.scenes,w.compositor.snapshot());saved=load_project(project);assert saved['scenes'][0]['single']['media']['pdf_page']==1
 # Multi-screen PDF keeps its page and source independent of the media list.
 c=w.compositor;original=copy.deepcopy(w.lists);c.grid(2,2);w.files.setCurrentRow(0);c.use_selected_file();layer=c.selected()
 wait(lambda:not layer.pending and not layer.transition and layer.decks[layer.active].kind=='pdf')
 assert w.lists==original
 w.screen.setFocus();QTest.keyClick(w.screen,Qt.Key_End);wait(lambda:layer.decks[layer.active].config.get('pdf_page')==2)
 assert w.lists==original
 c.enable.setChecked(False);w.stop();w.lists[0]['items'][0]['pdf_page']=0;w.play_selected();wait(lambda:not w.pending and not w.transition)
 w.pdf_auto.setChecked(True);wait(lambda:w.current_item()['pdf_page']>=1);w.pdf_auto.setChecked(False)
 # Failed PowerPoint detection must preserve the current PDF output.
 before=w.current;w.lists[0]['items'].append({'path':folder+'/deck.pptx','seconds':5});open(folder+'/deck.pptx','wb').close()
 with patch('presentations.powerpoint_available',return_value=(False,'未安裝 PowerPoint')):w.request((0,1))
 assert w.current==before and w.running
 # Route native startup and step commands without requiring Office in this environment.
 calls=[]
 with patch('presentations.powerpoint_available',return_value=(True,'ok')),patch.object(w.presentations.worker,'submit',side_effect=lambda *args:calls.append(args)):
  w.request((0,1));token=w.presentations.generation
  w.presentations.native_opened({'_token':token,'slide':1,'total':3,'click':0,'clicks':2,'state':1});assert w.presentations.active
  w.advance();assert calls[-1][0]=='next';native_cue=c.capture_cue('原生PPT');assert native_cue['single']['media']['ppt_slide']==1
  c.enable.setChecked(True);assert not w.presentations.active and w.current is None
  c.enable.setChecked(False)
  # An asynchronous Office open must survive list edits without an invalid index.
  w.request((0,1));token=w.presentations.generation;w.lists[0]['items'].pop()
  w.presentations.native_opened({'_token':token,'slide':2,'total':3,'click':1,'clicks':2,'state':1})
  assert w.presentations.active and w.current_item()['ppt_slide']==2
  w.stop()
 w.close()
# Documented COM contract: animation clicks occur before advancing to the next slide.
class Slides:Count=3
class Slide:SlideIndex=1
class View:
 def __init__(self):self.Slide=Slide();self.State=1;self.index=0;self.log=[]
 def GetClickCount(self):return 2
 def GetClickIndex(self):return self.index
 def GotoClick(self,i):self.index=i;self.log.append(('click',i))
 def Next(self):self.Slide.SlideIndex+=1;self.index=0;self.log.append(('next',))
 def Previous(self):self.Slide.SlideIndex=max(1,self.Slide.SlideIndex-1)
 def GotoSlide(self,i,reset):self.Slide.SlideIndex=i;self.index=0
 def Exit(self):self.log.append(('exit',))
class Win:
 HWND=123
 def __init__(self):self.View=View()
class Settings:
 def __init__(self):self.window=Win()
 def Run(self):return self.window
class Presentation:
 def __init__(self):self.Slides=Slides();self.SlideShowSettings=Settings();self.closed=False
 def Close(self):self.closed=True
class Presentations:
 def Open(self,*args):self.args=args;self.result=Presentation();return self.result
class Office:
 AutomationSecurity=1
 def __init__(self):self.Presentations=Presentations()
office=Office();session=PowerPointSession(office,lambda *args:None);session.start('/tmp/test.pptx','DISPLAY1')
assert office.Presentations.args[1:]==(True,True,False) and office.AutomationSecurity==1
settings=office.Presentations.result.SlideShowSettings;assert settings.ShowWithAnimation==-1 and settings.ShowWithNarration==-1
session.command('next');session.command('next');session.command('next');assert session.window.View.log==[('click',1),('click',2),('next',)]
session.command('goto',3);assert session.state()['slide']==3
session.command('black');assert session.state()['state']==3
session.close();assert office.Presentations.result.closed
print('PASS native PDF rendering/pages, pen routing and editing focus, CUE/save/load, multi independence, auto PDF, PowerPoint lifecycle/animation COM contract')
