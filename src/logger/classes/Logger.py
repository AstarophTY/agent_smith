from typing import Optional, Any
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from os import getenv
import logging
import json
import sys

from ..errors import UnInitializedError, AlreadyInitializedError
from .ColorFormatter import ColorFormatter


class Logger:
    _initialized = False
    _logger: Optional[logging.Logger] = None
    _base_path = Path("evaluations")
    _stdout_file: Optional[Path] = None
    _stderr_file: Optional[Path] = None

    @classmethod
    def setup(cls, eval_type: str, task_id: str) -> None:
        """Initialise the evaluation directory
            and configure logging for the singleton.

        Args:
            eval_type (str): Name of the sub‑directory
                that identifies the evaluation type
            task_id (str): Unique identifier for this specific run; used as the
                innermost directory name to avoid log collisions.

        """
        if cls._initialized:
            raise AlreadyInitializedError(
                "Logger has already been initialised; call get() instead.")

        load_dotenv()
        log_level = getenv("LOG_LEVEL", "INFO").upper()

        cls._base_path.mkdir(exist_ok=True)
        setattr(Logger, "log_dir", cls._create_eval_dir(eval_type, task_id))

        cls._stdout_file = getattr(Logger, "log_dir") / "stdout.log"
        cls._stderr_file = getattr(Logger, "log_dir") / "stderr.log"

        cls._logger = logging.getLogger("agent-smith")
        cls._logger.setLevel(log_level)

        console_formatter = ColorFormatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        console_out = logging.StreamHandler(sys.stdout)
        console_out.setLevel(logging.DEBUG)
        console_out.addFilter(lambda r: r.levelno == logging.INFO)
        console_out.setFormatter(console_formatter)

        console_err = logging.StreamHandler()
        console_err.setLevel(logging.DEBUG)
        console_err.addFilter(lambda r: r.levelno != logging.INFO)
        console_err.setFormatter(console_formatter)

        file_out = logging.FileHandler(
            str(cls._stdout_file), mode="w", encoding="utf-8")
        file_out.setLevel(logging.DEBUG)
        file_out.addFilter(lambda r: r.levelno == logging.INFO)
        file_out.setFormatter(file_formatter)

        file_err = logging.FileHandler(
            str(cls._stderr_file), mode="w", encoding="utf-8")
        file_err.setLevel(logging.DEBUG)
        file_err.addFilter(lambda r: r.levelno != logging.INFO)
        file_err.setFormatter(file_formatter)

        cls._logger.addHandler(console_out)
        cls._logger.addHandler(console_err)
        cls._logger.addHandler(file_out)
        cls._logger.addHandler(file_err)
        cls._initialized = True

    @classmethod
    def get(cls) -> logging.Logger:
        """Provide the logger object for printing.

        Raises:
            UnInitializedError: Raise when you dont have execute Logger.setup.

        Returns:
            logging.Logger: Return instance logger of logging module.
        """
        if not cls._initialized:
            raise UnInitializedError(
                "Logger must be initialized via Logger.setup() before use.")

        assert cls._logger is not None

        return cls._logger

    @classmethod
    def _create_eval_dir(
        cls, eval_type: str, task_id: str
    ) -> Path:
        """
        Create evaluation directory structure:
        ./evaluations/EVAL_TYPE/YYYY-MM-DD_HH-MM-SS/task_id/

        Args:
            eval_type: Type of evaluation
            task_id: Task identifier

        Returns:
            Path to the created task directory
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_dir = cls._base_path / eval_type / timestamp / task_id
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    @classmethod
    def save_task_result(
        cls,
        task_data: dict[str, Any],
        solution_data: dict[str, Any],
    ) -> Any:
        """
        Save evaluation results to structured directory.

        Args:
            eval_type: Type of evaluation
            task_id: Task identifier
            task_data: Task information to save as task.json
            solution_data: Solution data to save as solution.json
            stdout: Standard output to save as stdout.log
            stderr: Standard error to save as stderr.log

        Returns:
            Path to the task directory where files were saved
        """
        log_dir = getattr(Logger, "name")

        (log_dir / "task.json").write_text(
            json.dumps(task_data, indent=2)
        )
        (log_dir / "solution.json").write_text(
            json.dumps(solution_data, indent=2)
        )

        return log_dir

    @classmethod
    def debug(cls, msg: str, *args: Any, **kwargs: Any) -> None:
        cls.get().debug(msg, *args, **kwargs)

    @classmethod
    def info(cls, msg: str, *args: Any, **kwargs: Any) -> None:
        cls.get().info(msg, *args, **kwargs)

    @classmethod
    def warning(cls, msg: str, *args: Any, **kwargs: Any) -> None:
        cls.get().warning(msg, *args, **kwargs)

    @classmethod
    def error(cls, msg: str, *args: Any, **kwargs: Any) -> None:
        cls.get().error(msg, *args, **kwargs)

    @classmethod
    def critical(cls, msg: str, *args: Any, **kwargs: Any) -> None:
        cls.get().critical(msg, *args, **kwargs)
