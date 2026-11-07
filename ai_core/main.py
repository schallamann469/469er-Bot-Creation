"""Command-line entry point for the local HTTP service."""

import logging
import os
from http.server import ThreadingHTTPServer

from .api import create_server
from .config import load_language_config
from .language import OllamaProvider, provider_from_environment
from .providers import MockProvider
from .service import CoreService


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sources = [item.strip() for item in os.getenv("VISIONARY_SOURCES", "").split(",") if item.strip()]
    language_config = load_language_config(os.getenv("AI_CORE_CONFIG", "config.yaml"))
    if os.getenv("AI_LANGUAGE_PROVIDER", "").strip():
        language_provider = provider_from_environment()
    elif language_config.provider == "mock":
        language_provider = MockProvider()
    else:
        language_provider = OllamaProvider(
            endpoint=language_config.endpoint,
            model=language_config.model,
            timeout_seconds=language_config.timeout_seconds,
        )
    service = CoreService(
        os.getenv("AI_CORE_DATABASE", "data/knowledge.sqlite3"),
        configured_sources=sources,
        language_provider=language_provider,
        system_prompt=language_config.system_prompt,
        language_timeout=language_config.timeout_seconds,
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
