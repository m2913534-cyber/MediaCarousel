import unittest,tempfile,json
from pathlib import Path
from model import following,save_project,load_project,clip_bounds,normalize_layer
class Tests(unittest.TestCase):
    def setUp(self):self.lists=[{'name':'A','items':[{'path':'a','seconds':5},{'path':'b','seconds':3}]},{'name':'empty','items':[]},{'name':'B','items':[{'path':'c','seconds':2}]}]
    def test_modes(self):
        self.assertEqual(following(self.lists,(0,1),'清單循環'),(0,0));self.assertEqual(following(self.lists,(0,1),'所有清單輪播'),(2,0));self.assertEqual(following(self.lists,(2,0),'所有清單輪播'),(0,0));self.assertEqual(following(self.lists,(0,0),'所有清單輪播',True),(2,0));self.assertIsNone(following(self.lists,(0,1),'播放一次'));self.assertEqual(following(self.lists,(0,1),'單檔循環'),(0,1));self.assertIsNone(following([], (0,0), '所有清單輪播'))
    def test_portable_project_and_scenes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp).resolve()/'show.mcarousel';media=Path(tmp).resolve()/'媒體.mp4';item={'path':str(media),'seconds':7.5,'start':2,'end':8,'gain':45,'mute':True}
            lists=[{'name':'現場','items':[item]}];layout=[normalize_layer({'kind':'camera','source':'device-1','name':'擷取卡','x':100,'y':80},1)]
            scenes=[{'name':'開場','layout':layout,'settings':{'volume':60}}]
            save_project(path,lists,{'effect':'淡入淡出'},scenes,layout);data=load_project(path)
            self.assertEqual(data['lists'],lists);self.assertEqual(data['layout'],layout);self.assertEqual(data['scenes'],scenes);self.assertNotIn(str(media),path.read_text(encoding='utf-8'))
    def test_v1_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'v1.mcarousel';p.write_text(json.dumps({'version':1,'lists':self.lists,'settings':{}}));data=load_project(p)
            self.assertEqual(data['layout'],[]);self.assertEqual(data['lists'][0]['items'][0]['gain'],100)
    def test_clips(self):
        self.assertEqual(clip_bounds({'start':2,'end':6},10000),(2000,6000));self.assertEqual(clip_bounds({'start':2,'end':0},10000),(2000,10000));self.assertEqual(clip_bounds({'start':50,'end':80},10000),(9999,10000))
    def test_reject_invalid_layout_and_clip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.mcarousel'
            for data in [{'version':2,'lists':self.lists,'layout':[{}]*13},{'version':2,'lists':[{'name':'x','items':[{'path':'a','start':8,'end':2}]}]}]:
                p.write_text(json.dumps(data))
                with self.assertRaises(ValueError):load_project(p)
    def test_geometry_clamp(self):
        c=normalize_layer({'x':1900,'y':1000,'w':600,'h':400,'gain':float('nan')},1);self.assertEqual((c['x'],c['y'],c['gain']),(1320,680,100))
if __name__=='__main__':unittest.main()
