import logging

COLORS: dict[int, str] = {
    logging.DEBUG:    "\033[35m",
    logging.INFO:     "\033[32m",
    logging.WARNING:  "\033[33m",
    logging.ERROR:    "\033[31m",
    logging.CRITICAL: "\033[31;1m"
}

RESET: str = "\033[0m"
