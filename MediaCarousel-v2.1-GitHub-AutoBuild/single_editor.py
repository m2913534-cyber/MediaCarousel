"""Single-output media transforms, independent from compositor tile geometry."""
from PySide6.QtCore import Qt,QPointF
from PySide6.QtGui import QColor,QPen
from PySide6.QtWidgets import QGraphicsRectItem,QGraphicsItem

class SingleHandle(QGraphicsRectItem):
    def __init__(self,editor):
        super().__init__(-18,-18,18,18,editor);self.editor=editor
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations);self.setBrush(QColor('#6ee7d4'));self.setPen(QPen(Qt.NoPen));self.setCursor(Qt.SizeFDiagCursor)
    def paint(self,painter,option,widget=None):
        if widget is None or not widget.property('clean_output'):super().paint(painter,option,widget)
    def mousePressEvent(self,event):
        self.origin=event.scenePos();self.initial=self.editor.values();event.accept()
    def mouseMoveEvent(self,event):
        x,y,z=self.initial;delta=event.scenePos()-self.origin;r=self.editor.host.screen.sceneRect()
        zoom=z+(delta.x()*r.width()+delta.y()*r.height())/(r.width()**2+r.height()**2)
        self.editor.apply(x,y,zoom);event.accept()
    def mouseReleaseEvent(self,event):self.editor.host.persist_session();event.accept()

class SingleEditor(QGraphicsRectItem):
    def __init__(self,host):
        super().__init__(host.screen.canvas_root);self.host=host;self.enabled=False
        self.setZValue(100000);self.setPen(QPen(QColor('#6ee7d4'),2));self.setCursor(Qt.SizeAllCursor)
        self.handle=SingleHandle(self);self.hide()
    def paint(self,painter,option,widget=None):
        if widget is None or not widget.property('clean_output'):super().paint(painter,option,widget)
    def values(self):
        c=self.host.decks[self.host.active].config
        return c.get('single_x',0),c.get('single_y',0),c.get('single_zoom',1)
    def sync(self):
        h=self.host
        visible=self.enabled and not h.compositor.enabled and h.current is not None and not h.pending and not h.transition
        self.setVisible(visible)
        if visible:
            x,y,z=self.values();r=h.screen.sceneRect();self.setPos(x*r.width(),y*r.height());self.setRect(0,0,r.width()*z,r.height()*z);self.handle.setPos(self.rect().bottomRight())
    def apply(self,x,y,zoom):
        h=self.host
        if h.current is None or h.pending or h.transition or h.compositor.enabled:return
        c={'single_x':max(-4,min(4,x)),'single_y':max(-4,min(4,y)),'single_zoom':max(.05,min(8,zoom))}
        h.decks[h.active].config.update(c);p,i=h.current;h.lists[p]['items'][i].update(c)
        h.decks[h.active].apply_transform();self.sync()
    def mousePressEvent(self,event):self.origin=event.scenePos();self.initial=self.values();event.accept()
    def mouseMoveEvent(self,event):
        x,y,z=self.initial;delta=event.scenePos()-self.origin;r=self.host.screen.sceneRect()
        self.apply(x+delta.x()/r.width(),y+delta.y()/r.height(),z);event.accept()
    def mouseReleaseEvent(self,event):self.host.persist_session();event.accept()
    def wheelEvent(self,event):
        x,y,z=self.values();r=self.host.screen.sceneRect();anchor=event.scenePos()
        new=max(.05,min(8,z*(1.1 if event.delta()>0 else 1/1.1)));ratio=new/z
        self.apply(anchor.x()/r.width()+(x-anchor.x()/r.width())*ratio,anchor.y()/r.height()+(y-anchor.y()/r.height())*ratio,new)
        self.host.persist_session();event.accept()
