"""One temporary comment target, anchored to the app rather than the window."""
import math
from annotations import position


class CommentPointer:
    def __init__(self):
        self.token=0; self.phase='idle'; self.cursor=None; self.target=None
        self.project=None; self.revision=None

    def start(self,project,revision,cursor):
        self.token+=1; self.phase='following'; self.cursor=cursor; self.target=None
        self.project=project; self.revision=revision

    def move(self,cursor):
        if self.phase=='following': self.cursor=cursor

    def place(self,space,x,y):
        if self.phase!='following': return False
        self.target={'point':space.point(x,y),'frame':dict(space.frame),'revision':self.revision}
        self.phase='placed'; return True

    def head(self,geometry,origin):
        if self.phase=='following': return self.cursor
        if self.phase=='placed':
            x,y=position(self.target['point'],self.target['frame'],geometry)
            return (origin[0]+x,origin[1]+y)
        return None

    def clear(self,token=None):
        if token is not None and token!=self.token: return False
        self.token+=1; self.phase='idle'; self.target=None; self.cursor=None
        return True


def paint_arrow(cr,tail,head):
    """Thin coral line, circular composer anchor and a filled triangle tip."""
    if tail is None or head is None: return
    tx,ty=tail; hx,hy=head
    cr.save(); cr.set_source_rgb(1,98/255,90/255); cr.set_line_width(1); cr.set_line_cap(1)
    cr.move_to(tx,ty); cr.line_to(hx,hy); cr.stroke()
    cr.arc(tx,ty,3,0,2*math.pi); cr.fill()
    distance=math.hypot(hx-tx,hy-ty)
    if distance>6:
        ux,uy=(hx-tx)/distance,(hy-ty)/distance
        cr.move_to(hx,hy); cr.line_to(hx-7*ux-3*uy,hy-7*uy+3*ux)
        cr.line_to(hx-7*ux+3*uy,hy-7*uy-3*ux); cr.close_path(); cr.fill()
    cr.restore()
