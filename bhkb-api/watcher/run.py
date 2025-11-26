from __future__ import annotations

import logging
import threading

from prometheus_client import start_http_server

from app.watcher.config import WatcherSettings
from app.watcher.service import Watcher, install_signal_handlers


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = WatcherSettings()
    stop_event = threading.Event()
    install_signal_handlers(stop_event)
    start_http_server(settings.PROM_PORT)
    watcher = Watcher(settings, stop_event)
    watcher.logger.info("watcher started", extra={"run_id": watcher.run_id})
    watcher.run_forever()


if __name__ == "__main__":
    main()
