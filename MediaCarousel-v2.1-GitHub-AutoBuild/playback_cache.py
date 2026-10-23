"""Bounded, silent preparation of next video frames using the existing idle decks."""
import time
from pathlib import Path
from PySide6.QtCore import QTimer
from model import following,clip_bounds,is_still,is_pdf,is_powerpoint

def signature(item):
    return tuple(item.get(key,0 if key!='path' else '') for key in ('path','start','end','_resume_ms'))

def file_stamp(item):
    stat=Path(item['path']).stat();return stat.st_mtime_ns,stat.st_size

class Preroll:
    def __init__(self,player):self.player=player;self.generation=0;self.reset()
    def reset(self):
        self.generation+=1;self.warming=False;self.ready=False;self.positioned=False;self.target=0;self.failed=False;self.pause_queued=False
    def positioned_at(self,target):self.target=target;self.positioned=True
    def observe(self,frame):
        if not frame.isValid() or not self.positioned:return False
        # Seek completion must precede presentation; an early frame at file time 0
        # is never used for a clip with a later in-point.
        stamp=frame.startTime()
        if (self.warming or not self.ready) and self.target>0 and (stamp>=0 and stamp<self.target*1000 or stamp<0 and self.player.position()<self.target):return False
        self.ready=True
        if self.warming and not self.pause_queued:
            self.pause_queued=True;generation=self.generation
            QTimer.singleShot(0,lambda:self.pause_if_warming(generation))
        return True
    def pause_if_warming(self,generation):
        if generation==self.generation and self.warming and self.ready:self.player.pause()
    def activate(self):self.warming=False;self.player.play()

class NextVideoCache:
    """At most two paused preparations, and only one decoder warming at a time.

    Multi-screen warming is limited to the last two seconds before a source ends.
    Cache failures stay off-air and fall back to the normal load on request.
    """
    def __init__(self,host):
        self.host=host;self.jobs={};self.cooldown={};self.timer=QTimer(host);self.timer.timeout.connect(self.tick);self.timer.start(250)
    def discard(self,owner,clear=True):
        job=self.jobs.pop(owner,None)
        if job and clear and job['index']!=owner.active and not owner.pending and not owner.transition:owner.decks[job['index']].clear()
    def take(self,owner,target,item):
        job=self.jobs.pop(owner,None)
        if job and job['target']==target and job['signature']==signature(item) and job['source'] is item and job['index']==1-owner.active:
            deck=owner.decks[job['index']]
            try:
                if not deck.preroll.failed and file_stamp(item)==job.get('stamp'):return deck
            except OSError:pass
        return None
    def plan(self,owner):
        h=self.host
        if not owner.running or owner.current is None or owner.pending or owner.transition or owner.held:return None
        if owner is h:
            if h.cue_item is not None:return None
            target=following(h.lists,h.current,h.mode.currentText())
            if target is None:return None
            item=h.lists[target[0]]['items'][target[1]];direct=h.effect.currentText()=='直接切換'
        else:
            target=owner.next_target()
            if target is None:return None
            items=owner.source_items()
            if not 0<=target[1]<len(items):return None
            item=items[target[1]];direct=owner.panel.performance.isChecked() or h.effect.currentText()=='直接切換'
            d=owner.decks[owner.active]
            if d.kind=='video':
                _,end=clip_bounds(d.config,d.player.duration())
                if not end or end-d.player.position()>2000:return None
            elif d.kind=='image':
                if d.config.get('seconds',5)-owner.elapsed>2:return None
            else:return None
        if target==owner.current and direct:return None
        if is_still(item) or is_pdf(item) or is_powerpoint(item):return None
        return target,item
    def tick(self):
        h=self.host
        if h.presentations.active or h.presentations.starting:owners=[]
        else:owners=[l for l in h.compositor.layers if l.c['kind']=='playlist'] if h.compositor.enabled else [h]
        plans={owner:self.plan(owner) for owner in owners};now=time.monotonic()
        for owner,job in list(self.jobs.items()):
            plan=plans.get(owner);deck=owner.decks[job['index']]
            invalid=not plan or plan[0]!=job['target'] or signature(plan[1])!=job['signature'] or plan[1] is not job['source']
            failed=deck.preroll.failed or not deck.preroll.ready and now-job['started']>5
            if invalid or failed:
                if failed:self.cooldown[(id(owner),job['signature'])]=now+10
                self.discard(owner)
        self.cooldown={key:until for key,until in self.cooldown.items() if until>now}
        if len(self.jobs)>=2 or any(not owner.decks[job['index']].preroll.ready for owner,job in self.jobs.items()):return
        for owner,plan in plans.items():
            if owner in self.jobs or not plan:continue
            target,item=plan;key=signature(item)
            if (id(owner),key) in self.cooldown:continue
            index=1-owner.active;deck=owner.decks[index]
            self.jobs[owner]={'index':index,'target':target,'signature':key,'source':item,'started':now}
            try:
                self.jobs[owner]['stamp']=file_stamp(item)
                if owner is h:deck.load(item['path'],h.fit.currentIndex(),item,warm=True)
                else:deck.load(item,warm=True)
                deck.source_ref=item
                if deck.kind=='video':deck.player.play()
            except Exception:deck.preroll.failed=True
            break
