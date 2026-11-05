"""Experimental embedding boundary; no project, agent or collaboration ownership."""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import os
import signal
import subprocess


@dataclass(frozen=True)
class AppSpec:
    argv: tuple
    width: int = 460
    height: int = 600

    def __post_init__(self):
        if not self.argv or not (120 <= self.width <= 4096 and 120 <= self.height <= 4096):
            raise ValueError('An executable and logical dimensions from 120 to 4096 are required')


class PreviewBackend(Protocol):
    """The future viewport owns transforms; a backend owns surfaces and lifecycle.

    Dimensions are logical app dimensions. Neither zoom nor host allocation may
    rewrite them. Input transformations belong to the viewport/widget allocation,
    not ad-hoc synthetic input sent to the child.
    """
    widget: object

    def start(self, spec: AppSpec, runtime: Path, report: Path): ...
    def stop(self): ...


class CasildaBackend:
    def __init__(self):
        import gi
        gi.require_version('Casilda', '1.0')
        from gi.repository import Casilda
        # No public socket: only the child that receives this connected FD joins.
        self.widget = Casilda.Compositor()
        self.process = None

    def start(self, spec, runtime, report):
        if self.process is not None:
            raise RuntimeError('Stop the previous preview before starting another')
        env = dict(os.environ)
        for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'WAYLAND_SOCKET'):
            env.pop(key, None)
        env.update(GDK_BACKEND='wayland', GTK_A11Y='none')
        for key in ('CONFIG', 'DATA', 'CACHE'):
            path = runtime / key.lower()
            path.mkdir(parents=True, exist_ok=True)
            env['XDG_' + key + '_HOME'] = str(path)
        env['CENTAUR_GTK4_PROBE_REPORT'] = str(report)
        fd = self.widget.get_client_socket_fd()
        if fd < 0:
            raise RuntimeError('Casilda did not provide a client connection')
        try:
            env['WAYLAND_SOCKET'] = str(fd)
            self.process = subprocess.Popen(
                [*spec.argv, '--width', str(spec.width), '--height', str(spec.height)],
                env=env, pass_fds=(fd,), start_new_session=True, cwd=runtime)
        finally:
            os.close(fd)

    def stop(self):
        process, self.process = self.process, None
        if process is None:
            return
        try:
            # A separate process group also covers helpers belonging to the app.
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=0.8)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=0.8)
