"""Asynchronous native PDF page rendering with bounded raster size."""
from pathlib import Path
from PySide6.QtCore import QObject,Signal,QSize,Qt
from PySide6.QtGui import QImage,QPainter
from PySide6.QtPdf import QPdfDocument,QPdfPageRenderer

class PdfSource(QObject):
    ready=Signal(QImage,int,int)
    failed=Signal(str)
    def __init__(self):
        super().__init__();self.document=QPdfDocument(self);self.renderer=QPdfPageRenderer(self);self.renderer.setRenderMode(QPdfPageRenderer.MultiThreaded)
        self.renderer.pageRendered.connect(self.rendered);self.path=None;self.page=0;self.count=0;self.request_id=-1;self.target=QSize(1920,1080);self.loading=False
    def close(self):
        self.path=None;self.count=0;self.loading=False;self.request_id=-1;self.renderer.setDocument(None);self.document.close()
    def load(self,path,page=0,target=None):
        self.close();error=self.document.load(str(Path(path).resolve()))
        if error!=QPdfDocument.Error.None_:
            if error in (QPdfDocument.Error.IncorrectPassword,QPdfDocument.Error.UnsupportedSecurityScheme):raise ValueError('此 PDF 有密碼或安全限制，請先另存可讀取版本。')
            raise ValueError('PDF 無法開啟：'+str(error))
        self.count=self.document.pageCount()
        if self.count<1:raise ValueError('PDF 沒有可顯示頁面。')
        self.path=str(path);self.target=target or QSize(1920,1080);self.renderer.setDocument(self.document);self.set_page(page)
    def set_page(self,page):
        if not self.count:return False
        page=max(0,min(self.count-1,int(page)));self.page=page
        points=self.document.pagePointSize(page)
        if points.isEmpty():self.failed.emit('PDF 頁面尺寸無效');return False
        scale=max(self.target.width()/points.width(),self.target.height()/points.height())
        width,height=max(1,round(points.width()*scale)),max(1,round(points.height()*scale))
        if max(width,height)>4096:
            factor=4096/max(width,height);width=max(1,round(width*factor));height=max(1,round(height*factor))
        self.loading=True;self.request_id=self.renderer.requestPage(page,QSize(width,height));return True
    def step(self,reverse=False):
        target=self.page+(-1 if reverse else 1)
        return self.set_page(target) if 0<=target<self.count else False
    def rendered(self,page,size,image,options,request_id):
        if self.path is None or request_id!=self.request_id:return
        self.loading=False
        if image.isNull():self.failed.emit('PDF 頁面繪製失敗');return
        paper=QImage(image.size(),QImage.Format_RGB32);paper.fill(Qt.white);p=QPainter(paper);p.drawImage(0,0,image);p.end()
        self.ready.emit(paper,page,self.count)
