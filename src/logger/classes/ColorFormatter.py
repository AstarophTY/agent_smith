import logging
import copy

from ..constant import COLORS, RESET


class ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record_copy = copy.copy(record)
        color = COLORS.get(record_copy.levelno, "")
        record_copy.levelname = f"{color}{record_copy.levelname}{RESET}"
        return super().format(record_copy)
