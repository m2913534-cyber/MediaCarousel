import os,tempfile,copy,math,struct
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QPushButton
from PySide6.QtGui import QImage,QColor
from PySide6.QtCore import Qt,QByteArray
from PySide6.QtMultimedia import QAudioFormat,QAudioBuffer
from app import Window
from model import save_project,load_project
from audio_meter import levels
app=QApplication([]);w=Window();w.session_ready=False;w.session_timer.stop();w.effect.setCurrentText('直接切換');c=w.compositor
with tempfile.TemporaryDirectory() as folder:
 path=folder+'/image.png';im=QImage(300,200,QImage.Format_RGB32);im.fill(QColor('red'));im.save(path)
 w.lists=[{'name':'來源','items':[{'path':path,'seconds':10,'start':0,'end':0,'gain':32,'mute':True}]}];w.refresh_groups();w.files.setCurrentRow(0)
 original=copy.deepcopy(w.lists);c.grid(2,2);assert w.lists==original
 for i in range(4):
  c.list.setCurrentRow(i);c.use_selected_file();c.layers[i].tick(1)
 assert w.lists==original and len(c.layers)==4
 assert not any(b.text()=='＋照片／影片' for b in c.findChildren(QPushButton))
 c.layers[0].resize_to(500,400);c.layers[0].setPos(100,80);c.layers[0].c['gain']=44
 multi=c.capture_cue('多畫面');assert multi['layout'][0]['items'][0]['gain']==32
 w.stop();c.enable.setChecked(False);w.files.setCurrentRow(0);w.play_selected();w.single_editor.apply(.1,.2,.6);w.volume.setValue(61)
 single=c.capture_cue('單畫面');c.scenes=[multi,single];c.refresh_scenes()
 # A cue owns its source snapshot; changing/removing original playlists must not corrupt it.
 w.stop();w.lists=[{'name':'空清單','items':[]}];w.refresh_groups();w.volume.setValue(10)
 c.scene_list.setCurrentIndex(1);c.recall();assert not c.enabled and w.cue_item['single_zoom']==.6 and w.volume.value()==61
 w.single_editor.apply(.3,.1,.7);assert single['single']['media']['single_zoom']==.6
 c.scene_list.setCurrentIndex(0);c.recall();assert c.enabled and c.layers[0].pos().x()==100 and c.layers[0].c['gain']==44
 for l in c.layers:l.tick(1)
 assert all(l.decks[l.active].config['path']==path for l in c.layers)
 w.stop();c.enable.setChecked(False);w.add_black();assert w.files.item(0).text().startswith('黑畫面')
 w.play_selected();assert w.decks[w.active].image.pixmap().toImage().pixelColor(0,0).name()=='#000000'
 black=c.capture_cue('黑場');c.scenes.append(black)
 project=folder+'/show.mcarousel';save_project(project,w.lists,w.settings(),c.scenes,c.snapshot());data=load_project(project)
 assert data['scenes'][1]['single']['media']['path']==path
 assert data['scenes'][2]['single']['media']['path']=='media:black'
 w.restore_project_data(data);c.scene_list.setCurrentIndex(2);c.recall();assert w.current_item()['kind']=='black'
 # Known PCM levels: L=-6.02 dBFS, R=-12.04 dBFS. Cover all decoded PCM formats.
 for sf,code,values in [(QAudioFormat.Float,'f',[.5,.25,-.5,-.25]),(QAudioFormat.Int16,'h',[16384,8192,-16384,-8192]),(QAudioFormat.Int32,'i',[1073741824,536870912,-1073741824,-536870912]),(QAudioFormat.UInt8,'B',[192,160,64,96])]:
  fmt=QAudioFormat();fmt.setSampleRate(48000);fmt.setChannelCount(2);fmt.setSampleFormat(sf)
  buf=QAudioBuffer(QByteArray(struct.pack('<'+code*4,*values)),fmt);peak,rms=levels(buf)
  assert peak==[.5,.25] and rms==[.5,.25]
 c.meter.refresh();assert c.meter.db==[-60,-60]
 print('PASS no playlist growth, independent single/multi CUE recall and persistence, black media, PCM levels')
w.close()
