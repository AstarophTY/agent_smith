from typing import Optional, Any
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from os import getenv
from sys import stdout
import logging
import json


class Logger:
    _initialized = False
    _logger: Optional[logging.Logger] = None
    _base_path = Path("evaluations")

    @classmethod
    def _setup(cls):
        if cls._initialized:
            return

        load_dotenv()
        log_level = getenv("LOG_LEVEL", "INFO").upper()


        cls._base_path.mkdir(exist_ok=True)

        cls._logger = logging.getLogger("agent-smith")
        cls._logger.setLevel(log_level)

        cls._handler = logging.StreamHandler()
        cls._handler.setLevel(logging.INFO)

        cls._error_handler = logging.StreamHandler()
        cls._error_handler.setLevel(logging.ERROR)

        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        cls._handler.setFormatter(formatter)

        cls._logger.addHandler(cls._handler)
        cls._logger.addHandler(cls._error_handler)
        cls._initialized = True

    @classmethod
    def get(cls) -> logging.Logger:
        if not cls._initialized:
            cls._setup()

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
        eval_type: str,
        task_id: str,
        task_data: dict[str, Any],
        solution_data: dict[str, Any],
        stdout: str = "",
        stderr: str = "",
    ) -> Path:
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
        log_dir = cls._create_eval_dir(eval_type, task_id)

        (log_dir / "task.json").write_text(
            json.dumps(task_data, indent=2)
        )
        (log_dir / "solution.json").write_text(
            json.dumps(solution_data, indent=2)
        )

        if stdout:
            (log_dir / "stdout.log").write_text(stdout)
        if stderr:
            (log_dir / "stderr.log").write_text(stderr)

        return log_dir

    @classmethod
    def debug(cls, msg: str, *args, **kwargs) -> None:
        cls.get().debug(msg, *args, **kwargs)

    @classmethod
    def info(cls, msg: str, *args, **kwargs) -> None:
        cls.get().info(msg, *args, **kwargs)

    @classmethod
    def warning(cls, msg: str, *args, **kwargs) -> None:
        cls.get().warning(msg, *args, **kwargs)

    @classmethod
    def error(cls, msg: str, *args, **kwargs) -> None:
        cls.get().error(msg, *args, **kwargs)

    @classmethod
    def critical(cls, msg: str, *args, **kwargs) -> None:
        cls.get().critical(msg, *args, **kwargs)


if __name__ == "__main__":
    Logger.info("Salut tout le monde !")
    Logger.error("Salut tout le monde !")
    # Logger.save_task_result("TESt", "TEs", {"Test": 4}, {"5": "test"}, "Salut", "dwdw")
