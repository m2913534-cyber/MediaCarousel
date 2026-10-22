from pathlib import Path
import json, os, math
from copy import deepcopy
MODES = ['清單循環', '所有清單輪播', '單檔循環', '播放一次']
EFFECTS = ['淡入淡出', '淡出至黑再淡入', '向左滑動', '向右滑動', '縮放淡入', '直接切換', '隨機效果']
IMAGE_EXT = {'.jpg','.jpeg','.png','.bmp','.webp','.tif','.tiff','.gif'}
MAX_LAYERS = 12
PDF_EXT={'.pdf'}
PPT_EXT={'.ppt','.pptx','.pps','.ppsx'}
def is_pdf(item):return Path(item.get('path','')).suffix.lower() in PDF_EXT
def is_powerpoint(item):return Path(item.get('path','')).suffix.lower() in PPT_EXT

def is_still(item):return item.get('kind')=='black' or Path(item.get('path','')).suffix.lower() in IMAGE_EXT
def media_name(item):return item.get('name','黑畫面') if item.get('kind')=='black' else Path(item.get('path','')).name

def media_walk(value,fn):
    if isinstance(value,dict):
        if 'path' in value:fn(value)
        for child in value.values():media_walk(child,fn)
    elif isinstance(value,list):
        for child in value:media_walk(child,fn)

def following(lists, current, mode, reverse=False):
    available = [(p,i) for p,l in enumerate(lists) for i in range(len(l['items']))]
    if not available: return None
    if mode == '單檔循環': return current if current in available else available[0]
    if mode in ('清單循環','播放一次'): available = [x for x in available if x[0] == current[0]]
    if not available: return None
    if current not in available: return available[-1] if reverse else available[0]
    index = available.index(current) + (-1 if reverse else 1)
    if mode == '播放一次' and (index < 0 or index >= len(available)): return None
    return available[index % len(available)]

def number(value, default, low, high):
    try: value=float(value)
    except (TypeError,ValueError): value=default
    if not math.isfinite(value): value=default
    return max(low,min(high,value))

def clip_bounds(item, duration_ms):
    duration=max(0,int(duration_ms))
    start=min(int(number(item.get('start',0),0,0,86400)*1000),max(0,duration-1))
    end=int(number(item.get('end',0),0,0,86400)*1000) or duration
    return start,max(start+1,min(duration,end)) if duration else 0

def normalize_layer(c, list_count, width=1920, height=1080):
    c=dict(c)
    if c.get('kind','playlist') not in ('playlist','camera','screen','window'): raise ValueError('未知影像來源')
    for key,default,low,high in [('x',0,0,width),('y',0,0,height),('w',640,80,width),('h',360,45,height),('gain',100,0,100)]:
        c[key]=number(c.get(key,default),default,low,high)
    c['x']=min(c['x'],width-c['w']);c['y']=min(c['y'],height-c['h'])
    c['group']=int(number(c.get('group',0),0,0,max(0,list_count-1)))
    c['kind']=c.get('kind','playlist');c['name']=str(c.get('name','畫面'))[:120]
    c['mute']=bool(c.get('mute',False));c['fit']=bool(c.get('fit',True))
    return c

def save_project(path, lists, settings, scenes=None, layout=None):
    base=Path(path).parent
    data=deepcopy({'version':2,'lists':lists,'settings':settings,'scenes':scenes or [],'layout':layout or []})
    def relative(item):
        if item.get('kind')=='black':return
        try:item['path']=os.path.relpath(item['path'],base)
        except ValueError:pass
    media_walk(data,relative)
    tmp=Path(str(path)+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(path)

def load_project(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('version') not in (1,2) or not isinstance(data.get('lists'),list): raise ValueError('不支援的專案格式')
    for group in data['lists']:
        if not isinstance(group.get('name'),str) or not isinstance(group.get('items'),list):raise ValueError('清單資料錯誤')
        for item in group['items']:
            if not isinstance(item.get('path'),str):raise ValueError('媒體路徑錯誤')
    def absolute(item):
        if not isinstance(item['path'],str):raise ValueError('媒體路徑錯誤')
        if item.get('kind')!='black':item['path']=str((Path(path).parent/item['path']).resolve())
        item['seconds']=number(item.get('seconds',5),5,.5,86400)
        if is_pdf(item):item['pdf_page']=int(number(item.get('pdf_page',0),0,0,1000000))
        if is_powerpoint(item):
            item['ppt_slide']=int(number(item.get('ppt_slide',1),1,1,1000000));item['ppt_click']=int(number(item.get('ppt_click',0),0,0,1000000))
        item['start']=number(item.get('start',0),0,0,86400);item['end']=number(item.get('end',0),0,0,86400)
        if item['end'] and item['end']<=item['start']:raise ValueError('片段終點必須大於起點')
        item['gain']=number(item.get('gain',100),100,0,100);item['mute']=bool(item.get('mute',False))
    media_walk(data,absolute)
    def layout(value,settings):
        if not isinstance(value,list) or len(value)>MAX_LAYERS: raise ValueError('畫面數量必須介於 0–12')
        width=number(settings.get('canvas_width',1920),1920,80,4096)
        height=number(settings.get('canvas_height',1080),1080,45,4096)
        return [normalize_layer(c,len(data['lists']),width,height) for c in value]
    data['layout']=layout(data.get('layout',[]),data.get('settings',{})); scenes=data.get('scenes',[])
    if not isinstance(scenes,list):raise ValueError('場景資料錯誤')
    data['scenes']=[dict(s,name=str(s['name'])[:120],layout=layout(s['layout'],s.get('settings',{})),settings=s.get('settings',{})) for s in scenes]
    return data

