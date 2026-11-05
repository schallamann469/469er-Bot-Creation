"""Run: python -m yinyang_core  (Ctrl+C for graceful shutdown)."""
import signal
import threading

from .api import make_server
from .app import Core
from .config import Settings


def main():
    core = Core(Settings.from_env())
    core.start()
    server = make_server(core)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"listening on http://{server.server_address[0]}:{server.server_address[1]} (provider: mock)")
    stop.wait()
    core.lifecycle.stop()  # stop accepting + drain before closing the socket
    server.shutdown()
    server.server_close()
    core.stop()
    print("stopped")


if __name__ == "__main__":
    main()
