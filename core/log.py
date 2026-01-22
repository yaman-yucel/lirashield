"""
Logging configuration for LiraShield application.
"""

import logging
from datetime import datetime


class ColorFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: "\033[1;34m",
        logging.INFO: "\033[1;32m",
        logging.WARNING: "\033[1;33m",
        logging.ERROR: "\033[1;38;5;208m",
        logging.CRITICAL: "\033[1;31m",
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelno, self.RESET)
        log_time = datetime.fromtimestamp(record.created).strftime("%d-%m-%Y %H:%M:%S.%f")
        task_name = getattr(record, "taskName", None) or "N/A"
        s = (
            f"{self.RESET}[{log_time}] "
            f"{color}{record.levelname:<2}{self.RESET} | "
            f"Process: {record.process:<2} | "
            f"Thread: {record.threadName:<2} | "
            f"Task: {task_name:<6} | "
            f"Logger: {record.name:<2} | "
            f"Module: {record.module:<2} | "
            f"Line: {record.lineno:<2} | "
            f"{color}{record.getMessage()}{self.RESET}"
        )
        return s


class FileFormatter(logging.Formatter):
    def format(self, record):
        log_time = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        task_name = getattr(record, "taskName", None) or "N/A"
        s = (
            f"[{log_time}] "
            f"{record.levelname:<2} | "
            f"Process: {record.process:<2} | "
            f"Thread: {record.threadName:<2} | "
            f"Task: {task_name:<2} | "
            f"Logger: {record.name:<2} | "
            f"Module: {record.module:<2} | "
            f"Line: {record.lineno:<2} | "
            f"{record.getMessage()}"
        )
        return s


def get_logger(name: str = "app") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        stream_handler = logging.StreamHandler()

        stream_handler.setFormatter(ColorFormatter())
        logger.addHandler(stream_handler)
        file_handler = logging.FileHandler("worker.log")  #! STATIC
        file_handler.setFormatter(FileFormatter())
        logger.addHandler(file_handler)

    logger.setLevel("DEBUG")  #! STATIC
    logger.propagate = False
    return logger
