from typing import Any
from fnmatch import fnmatch
import subprocess
import shlex
import os
import re


class McpToolsSweBench:
    @staticmethod
    def run_command(command: str, workdir: str) -> Any:
        """Execute a shell command in the specified working directory.
        
        Args:
            command: The command string to execute.
            workdir: The working directory where the command will be run.
            
        Returns:
            The result of subprocess.run().
        """
        return subprocess.run(shlex.split(command), cwd=workdir)

    @staticmethod
    def read_file(filepath: str, start_line: int, end_line: int) -> str:
        """Read specific lines from a file with line numbers.
        
        Args:
            filepath: Path to the file to read.
            start_line: Starting line number (1-indexed).
            end_line: Ending line number (1-indexed, inclusive).
            
        Returns:
            A string containing the requested lines with line numbers prefixed.
        """
        with open(filepath, "r") as f:
            buffer = f.readlines()
            lines = buffer[start_line - 1:end_line]

            return "".join([
                f"{line_number + start_line}: {line_content}"
                for line_number, line_content in enumerate(lines)
            ])

    @staticmethod
    def edit_file(filepath: str, old_str: str, new_str: str) -> None:
        """Replace text content in a file.
        
        Args:
            filepath: Path to the file to edit.
            old_str: The text to search for and replace.
            new_str: The replacement text.
        """
        with open(filepath, "r") as f:
            buffer = f.read()
        
        new_content = buffer.replace(old_str, new_str)
        
        with open(filepath, "w") as f:
            f.write(new_content)

    @staticmethod
    def list_files(directory: str, pattern: str) -> list:
        """List files matching a pattern in a directory recursively.
        
        Args:
            directory: The root directory to search.
            pattern: A fnmatch pattern to filter files. Empty string matches all files.
            
        Returns:
            A list of file paths matching the pattern.
        """
        results = []
        for root, _, files in os.walk(directory):
            for fname in files:
                if fnmatch(fname, pattern) or len(pattern) <= 0:
                    results.append(os.path.join(root, fname))

        return results

    @staticmethod
    def search_code(pattern: str, file_pattern: str) -> str:
        """Search for a regex pattern in files matching a file pattern.
        
        Args:
            pattern: A regex pattern to search for.
            file_pattern: A fnmatch pattern to filter files to search.
            
        Returns:
            A string with matching results in format: filepath:line_number content.
        """
        checker = re.compile(pattern)
        matches = []

        for root, _, files in os.walk("."):
            for filename in files:
                if not fnmatch(filename, file_pattern):
                    continue

                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, "r") as handle:
                        for line_number, line_content in enumerate(handle, start=1):
                            if checker.search(line_content):
                                line_path = os.path.abspath(file_path)
                                matches.append(
                                    f"{line_path}:{line_number} "
                                    f"{line_content.rstrip()}"
                                )
                except (UnicodeDecodeError, IOError):
                    continue

        return "\n".join(matches)

    def run_tests(self) -> None:
        """Run the test suite using the agent-smith-test.sh script."""
        self.run_command("sh agent-smith-test.sh", ".")