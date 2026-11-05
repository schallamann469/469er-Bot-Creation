"""Command-line entry point for the local HTTP service."""

import logging
import os
from http.server import ThreadingHTTPServer

from .api import create_server
from .service import CoreService


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sources = [item.strip() for item in os.getenv("VISIONARY_SOURCES", "").split(",") if item.strip()]
    service = CoreService(
        os.getenv("AI_CORE_DATABASE", "data/knowledge.sqlite3"),
        configured_sources=sources,
    )
    server = create_server(
        service,
        os.getenv("AI_CORE_HOST", "127.0.0.1"),
        int(os.getenv("AI_CORE_PORT", "8000")),
    )
    logging.getLogger("ai_core").info("Service listening on %s:%s", *server.server_address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.getLogger("ai_core").info("Shutdown requested")
    finally:
        service.stop()
        server.server_close()


if __name__ == "__main__":
    main()
