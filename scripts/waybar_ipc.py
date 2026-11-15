"""Waybar 0.15 legacy workspace IPC -> Hyprland 0.57 Lua.

Runs as one blocking thread in the existing supervisor, with no polling or
extra process. Queries and compositor events retain the real IPC protocol.
Only the Waybar child receives the private instance path.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import tempfile
import threading


def translate(request):
    """Converte comandos antigos de workspace da Waybar para a sintaxe nova do Hyprland."""
    text = request.decode()
    for command in ('workspace','focusworkspaceoncurrentmonitor'):
        prefix = 'dispatch '+command+' '
        if text.startswith(prefix):
            value = text[len(prefix):].strip()
            value = int(value) if value.isdecimal() else value
            return ('eval hl.dispatch(hl.dsp.focus({workspace='+json.dumps(value)+'}))').encode()
    prefix = 'dispatch togglespecialworkspace'
    if text == prefix or text.startswith(prefix+' '):
        value = text[len(prefix):].strip()
        return ('eval hl.dispatch(hl.dsp.workspace.toggle_special('+json.dumps(value)+'))').encode()
    return request


@contextmanager
def compatible_environment():
    """Cria um socket intermediário entre a Waybar e o Hyprland que traduz os comandos."""
    environment = os.environ.copy()
    runtime = Path(environment['XDG_RUNTIME_DIR'])/'hypr'
    actual = runtime/environment['HYPRLAND_INSTANCE_SIGNATURE']
    with tempfile.TemporaryDirectory(prefix='rice-wb-',dir=runtime) as directory:
        private = Path(directory)
        (private/'.socket2.sock').symlink_to(actual/'.socket2.sock')
        with socket.socket(socket.AF_UNIX) as listener:
            path = private/'.socket.sock'
            listener.bind(str(path))
            listener.listen(8)
            stopping = threading.Event()
            def serve():
                while not stopping.is_set():
                    connection, _ = listener.accept()
                    with connection:
                        connection.settimeout(5)
                        try:
                            request = connection.recv(65536)
                            if not request:
                                continue
                            with socket.socket(socket.AF_UNIX) as upstream:
                                upstream.settimeout(5)
                                upstream.connect(str(actual/'.socket.sock'))
                                upstream.sendall(translate(request))
                                while block := upstream.recv(65536):
                                    connection.sendall(block)
                        except (OSError, ValueError) as exc:
                            try:
                                connection.sendall(('error: '+str(exc)).encode())
                            except OSError:
                                pass
            thread = threading.Thread(target=serve,name='waybar-lua-ipc',daemon=True)
            thread.start()
            environment['HYPRLAND_INSTANCE_SIGNATURE'] = private.name
            try:
                yield environment
            finally:
                stopping.set()
                with socket.socket(socket.AF_UNIX) as wake:
                    wake.connect(str(path))
                thread.join(timeout=6)
