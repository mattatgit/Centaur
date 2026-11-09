"""Saved canvas marks, anchored to the app through their existing frame field.

The reference rectangle encloses both the visible canvas and the full app.
Points and frame stay in [0,1], including when zoom/pan clips part of the app.
This preserves the existing coordinator/wire validation and legacy app marks.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class AnnotationSpace:
    left: float
    top: float
    width: float
    height: float
    canvas_width: float
    canvas_height: float
    frame: dict

    @classmethod
    def capture(cls,geometry,width,height):
        x,y=geometry['app_x'],geometry['app_y']
        aw=geometry['app_width']*geometry['scale']; ah=geometry['app_height']*geometry['scale']
        left,top=min(0,x),min(0,y)
        reference_width=max(width,x+aw)-left; reference_height=max(height,y+ah)-top
        if min(width,height,aw,ah,reference_width,reference_height)<=0: raise ValueError('Canvas is not allocated')
        return cls(left,top,reference_width,reference_height,width,height,
                   {'x':(x-left)/reference_width,'y':(y-top)/reference_height,
                    'width':aw/reference_width,'height':ah/reference_height})

    def point(self,x,y):
        # The canvas edge remains the drawing boundary, rather than the app.
        x=max(0,min(self.canvas_width,x)); y=max(0,min(self.canvas_height,y))
        return {'x':(x-self.left)/self.width,'y':(y-self.top)/self.height}


def position(point,frame,geometry):
    frame=frame or {'x':0,'y':0,'width':1,'height':1}
    values=[point['x'],point['y'],frame['x'],frame['y'],frame['width'],frame['height']]
    if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in values) or min(frame['width'],frame['height'])<=0:
        raise ValueError('Invalid annotation frame')
    return (geometry['app_x']+(point['x']-frame['x'])/frame['width']*geometry['app_width']*geometry['scale'],
            geometry['app_y']+(point['y']-frame['y'])/frame['height']*geometry['app_height']*geometry['scale'])
