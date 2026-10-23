"""Write audio properties only when they change, including every fade step.

Qt property signals invalidate the cache if another control changes the output.
No playback/seek/source operations belong in this path.
"""
class LiveAudio:
    def __init__(self,output):
        self.output=output;self.volume=None;self.muted=None
        output.volumeChanged.connect(self.invalidate_volume)
        output.mutedChanged.connect(self.invalidate_mute)
    def invalidate_volume(self,*_):self.volume=None
    def invalidate_mute(self,*_):self.muted=None
    def apply(self,volume,muted):
        volume=max(0.,min(1.,float(volume)));muted=bool(muted)
        if self.muted!=muted:
            self.output.setMuted(muted);self.muted=muted
        if self.volume!=volume:
            self.output.setVolume(volume);self.volume=volume
