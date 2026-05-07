import docker
from typing import Any
from docker.errors import APIError

from logger.classes.Logger import Logger


class Containerizer:
    """Manages the lifecycle of a Docker sandbox container.

    This class handles the creation, execution, and cleanup of a Docker
    container used as a sandbox environment. It ensures that only one
    container is active at a time for a given instance.

    Attributes:
        client (docker.DockerClient): The Docker client instance connected to
            the local environment.
        image (str): The name of the Docker image to use for the container.
        container (docker.models.containers.Container | None): The currently
            running container object, or None if no container is active.
    """

    def __init__(self) -> None:
        """Initializes the DockerSandboxManager.

        Args:
            image (str, optional): The Docker image to use for the sandbox.
                Defaults to "python:3.10-slim".
        """
        self.client = docker.from_env()
        self.container = None

    def up(self, image: str = "python:3.10-slim") -> None:
        """Starts a new Docker container.

        This method creates and starts a new container in detached mode.

        Raises:
            RuntimeError: If a container is already running (i.e.,
                self.container is not None).
        """
        if self.container is not None:
            raise RuntimeError(
                "Error: A container is already running. Please call down() "
                "first."
            )

        Logger.debug(f"Starting container with image '{image}'...")
        self.container = self.client.containers.run(
            image=image,
            command="/bin/bash",
            tty=True,
            detach=True
        )
        Logger.debug(
            f"Container {self.container.short_id} started successfully."
        )

    def down(self) -> None:
        """
        Stops and removes the current container, resetting the manager's state.

        If no container is currently running, the method will simply return
        without performing any actions. Any Docker API errors encountered
        during cleanup are caught and printed.
        """
        if self.container is None:
            Logger.error("No container is currently running.")
            return

        Logger.debug(
            f"Stopping and removing container {self.container.short_id}..."
        )
        try:
            self.container.stop()
            self.container.remove()
        except APIError as e:
            Logger.error(f"Docker API Error during cleanup: {e}")
        finally:
            self.container = None
            Logger.debug("Container cleaned up.")

    def cmd(self, command: str) -> dict[str, Any]:
        """Executes a command inside the running container.

        Args:
            command (str): The shell command to execute inside the container.

        Returns:
            dict[str, Any]: A dictionary containing 'stdout', 'stderr' and 'exit_code'.

        Raises:
            RuntimeError: If no container is currently running.
        """
        if self.container is None:
            raise RuntimeError(
                "Error: No container is running. Please call up() first."
            )

        # Wrap the command in a shell to support redirects (>), pipes (|), etc.
        # demux=True separates the stdout and stderr streams.
        exit_code, output = self.container.exec_run(
            cmd=["/bin/bash", "-c", command],
            demux=True,
        )

        if output is None:
            stdout_bytes, stderr_bytes = None, None
        else:
            stdout_bytes, stderr_bytes = output

        # Decode bytes to string. If a stream is empty, Docker SDK returns None
        # so we fallback to an empty string.
        stdout_str = stdout_bytes.decode("utf-8") if stdout_bytes else ""
        stderr_str = stderr_bytes.decode("utf-8") if stderr_bytes else ""

        return {
            "stdout": stdout_str,
            "stderr": stderr_str,
            "exit_code": exit_code,
        }


# --- Example usage ---
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    Logger.setup("test", "0")

    sandbox = Containerizer()

    sandbox.up()

    cmds = [
        "apt-get update",
        "apt-get install -y tree",
        "mkdir a",
        "mkdir a/b",
        "mkdir a/b/c",
        "mkdir a/b/d",
        "mkdir a/b/d/e",
        "tree a",
    ]
    for c in cmds:
        print(sandbox.cmd(c)["stdout"])

    sandbox.down()
