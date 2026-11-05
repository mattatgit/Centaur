"""Toolkit-independent app dimensions and canvas transform."""
from dataclasses import dataclass

ZOOM_MODES = ('50%', '75%', '100%', '125%', '150%', 'Fit')


@dataclass
class ViewportModel:
    app_width: int
    app_height: int
    mode: str = '100%'
    pan_x: float = 0
    pan_y: float = 0
    gutter: int = 96
    margin: int = 16

    def scale(self, width, height):
        if self.mode == 'Fit':
            return max(0.01, min(max(1, width - 2*self.margin) / self.app_width,
                                 max(1, height - 2*self.margin) / self.app_height))
        return float(self.mode.rstrip('%')) / 100

    def select(self, mode, width, height):
        if mode not in ZOOM_MODES:
            raise ValueError('Unsupported canvas zoom')
        before = self.scale(width, height)
        self.mode = mode
        after = self.scale(width, height)
        if mode == 'Fit':
            self.pan_x = self.pan_y = 0
        else:
            # Keep the same logical point under the viewport centre.
            self.pan_x *= after / before
            self.pan_y *= after / before
        self.geometry(width, height)

    def geometry(self, width, height):
        scale = self.scale(width, height)
        limit_x = max(0, (self.app_width * scale - width) / 2 + self.margin)
        limit_y = max(0, (self.app_height * scale - height) / 2 + self.margin)
        self.pan_x = max(-limit_x, min(limit_x, self.pan_x))
        self.pan_y = max(-limit_y, min(limit_y, self.pan_y))
        if self.mode == 'Fit':
            self.pan_x = self.pan_y = 0
        app_x = (width - self.app_width * scale) / 2 + self.pan_x
        app_y = (height - self.app_height * scale) / 2 + self.pan_y
        return dict(scale=scale, app_x=app_x, app_y=app_y,
                    app_width=self.app_width, app_height=self.app_height,
                    stage_x=app_x-self.gutter*scale, stage_y=app_y-self.gutter*scale,
                    stage_width=self.app_width+2*self.gutter,
                    stage_height=self.app_height+2*self.gutter,
                    pan_x=self.pan_x, pan_y=self.pan_y, mode=self.mode)

    def app_point(self, x, y, width, height):
        geometry = self.geometry(width, height)
        return ((x-geometry['app_x'])/geometry['scale'],
                (y-geometry['app_y'])/geometry['scale'])
