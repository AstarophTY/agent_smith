class SecurityException(Exception):
    """Raised when sandbox security checks fail."""


class FinalAnswerSignal(Exception):
    """Raised internally to stop execution after final_answer is called."""
