"""Start: python -m yinyang_core  (Strg+C für geordnetes Beenden)."""
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
    print(f"lauscht auf http://{server.server_address[0]}:{server.server_address[1]} (Anbieter: mock)")
    stop.wait()
    core.lifecycle.stop()  # keine neuen Aufgaben + laufende beenden, bevor der Socket schließt
    server.shutdown()
    server.server_close()
    core.stop()
    print("gestoppt")


if __name__ == "__main__":
    main()
