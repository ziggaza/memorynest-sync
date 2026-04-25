"""Configure root logger: daily rotating file + console."""

import logging
import logging.handlers
from pathlib import Path


def setup(log_dir: Path, level: int = logging.INFO) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotate at midnight, keep 30 days, filename: organizer_YYYY-MM-DD.log
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_dir / "organizer.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.namer  = lambda name: name.replace(
        "organizer.log.", "organizer_"
    )
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.WARNING)  # only warnings+ to console

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
