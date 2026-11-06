"""Independent width/height handles for single-output media."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QPen
from PySide6.QtWidgets import QGraphicsRectItem,QGraphicsItem
from model import single_transform

class SingleHandle(QGraphicsRectItem):
    def __init__(self,editor,horizontal,vertical):
        left=0 if horizontal<0 else -18 if horizontal>0 else -9
        top=0 if vertical<0 else -18 if vertical>0 else -9
        super().__init__(left,top,18,18,editor);self.editor=editor;self.horizontal=horizontal;self.vertical=vertical
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations);self.setBrush(QColor('#6ee7d4'));self.setPen(QPen(QColor('#163139'),1))
        self.setCursor(Qt.SizeHorCursor if not vertical else Qt.SizeVerCursor if not horizontal else Qt.SizeFDiagCursor if horizontal==vertical else Qt.SizeBDiagCursor)
    def paint(self,painter,option,widget=None):
        if widget is None or not widget.property('clean_output'):super().paint(painter,option,widget)
    def mousePressEvent(self,event):
        self.origin=event.scenePos();self.initial=self.editor.values();self.bounds=self.editor.base_rect();event.accept()
    def mouseMoveEvent(self,event):
        x,y,sx,sy=self.initial;delta=event.scenePos()-self.origin;r=self.editor.host.screen.sceneRect();b=self.bounds
        # Anchor the opposite edge, including letterbox offsets in the media's base rect.
        if self.horizontal:
            width=max(.05,min(8,sx+self.horizontal*delta.x()/max(1,b.width())))
            anchor=b.right() if self.horizontal<0 else b.left()
            x+=(sx-width)*anchor/r.width();sx=width
        if self.vertical:
            height=max(.05,min(8,sy+self.vertical*delta.y()/max(1,b.height())))
            anchor=b.bottom() if self.vertical<0 else b.top()
            y+=(sy-height)*anchor/r.height();sy=height
        self.editor.apply(x,y,sx,sy);event.accept()
    def mouseReleaseEvent(self,event):self.editor.host.persist_session();event.accept()

class SingleEditor(QGraphicsRectItem):
    def __init__(self,host):
        super().__init__(host.screen.canvas_root);self.host=host;self.enabled=False
        self.setZValue(100000);self.setPen(QPen(QColor('#6ee7d4'),2));self.setCursor(Qt.SizeAllCursor)
        self.handles={(x,y):SingleHandle(self,x,y) for x,y in [(-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)]}
        self.handle=self.handles[1,1];self.hide()
    def paint(self,painter,option,widget=None):
        if widget is None or not widget.property('clean_output'):super().paint(painter,option,widget)
    def values(self):return single_transform(self.host.decks[self.host.active].config)
    def base_rect(self):
        deck=self.host.decks[self.host.active];bounds=deck.item.mapRectToParent(deck.item.boundingRect())
        return bounds if not bounds.isEmpty() else self.host.screen.sceneRect()
    def sync(self):
        h=self.host
        visible=self.enabled and not h.compositor.enabled and not h.presentations.active and h.current is not None and not h.pending and not h.transition
        self.setVisible(visible)
        if visible:
            bounds=h.decks[h.active].root.mapRectToScene(self.base_rect());self.setPos(bounds.topLeft());self.setRect(0,0,bounds.width(),bounds.height())
            for (x,y),handle in self.handles.items():handle.setPos((x+1)*bounds.width()/2,(y+1)*bounds.height()/2)
    def apply(self,x,y,scale_x,scale_y=None):
        h=self.host
        if h.current is None or h.pending or h.transition or h.compositor.enabled or h.presentations.active:return
        if scale_y is None:scale_y=scale_x
        x,y,scale_x,scale_y=single_transform({'single_x':x,'single_y':y,'single_scale_x':scale_x,'single_scale_y':scale_y})
        c={'single_x':x,'single_y':y,'single_scale_x':scale_x,'single_scale_y':scale_y,'single_zoom':scale_x}
        h.decks[h.active].config.update(c);h.current_item().update(c)
        h.decks[h.active].apply_transform();self.sync()
    def mousePressEvent(self,event):self.origin=event.scenePos();self.initial=self.values();event.accept()
    def mouseMoveEvent(self,event):
        x,y,sx,sy=self.initial;delta=event.scenePos()-self.origin;r=self.host.screen.sceneRect()
        self.apply(x+delta.x()/r.width(),y+delta.y()/r.height(),sx,sy);event.accept()
    def mouseReleaseEvent(self,event):self.host.persist_session();event.accept()
    def wheelEvent(self,event):
        x,y,sx,sy=self.values();r=self.host.screen.sceneRect();anchor=event.scenePos();factor=1.1 if event.delta()>0 else 1/1.1
        horizontal=not event.modifiers() & Qt.AltModifier;vertical=not event.modifiers() & Qt.ShiftModifier
        nx=max(.05,min(8,sx*factor)) if horizontal else sx;ny=max(.05,min(8,sy*factor)) if vertical else sy
        self.apply(anchor.x()/r.width()+(x-anchor.x()/r.width())*nx/sx,anchor.y()/r.height()+(y-anchor.y()/r.height())*ny/sy,nx,ny)
        self.host.persist_session();event.accept()
