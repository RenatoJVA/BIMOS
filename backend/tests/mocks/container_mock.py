from pathlib import Path
from typing import Callable, Optional


class ContainerMock:
    def __init__(self):
        self.commands_executed = []
        self.return_code = 0
        self.output_callback = None

    def run(
        self,
        command: list[str],
        image: str = "",
        volumes: Optional[dict[str, str]] = None,
        workdir: str = "/workspace",
        on_output: Optional[Callable[[str], None]] = None,
        env: Optional[dict[str, str]] = None,
        stdin_text: Optional[str] = None,
        timeout: int = 7200,
    ) -> int:
        self.commands_executed.append({
            "command": command,
            "image": image,
            "volumes": volumes,
            "workdir": workdir,
            "timeout": timeout,
            "env": env,
            "stdin_text": stdin_text,
        })
        if on_output:
            on_output(f"Mock output for: {' '.join(command)}")
        return self.return_code

    def image_exists(self, image: str) -> bool:
        self.commands_executed.append({"action": "image_exists", "image": image})
        return True

    def build_image(
        self,
        dockerfile: str,
        tag: str,
        context: str = ".",
        on_output: Optional[Callable[[str], None]] = None,
    ) -> int:
        self.commands_executed.append({
            "action": "build_image",
            "dockerfile": dockerfile,
            "tag": tag,
            "context": context,
        })
        if on_output:
            on_output(f"Mock build of {tag}")
        return self.return_code

    def assert_command_contains(self, substring: str) -> None:
        for cmd in self.commands_executed:
            full_cmd = " ".join(cmd.get("command", []))
            if substring in full_cmd:
                return
        raise AssertionError(f"No command executed contains: {substring!r}")

    def assert_run_count(self, expected: int) -> None:
        actual = len(self.commands_executed)
        assert actual == expected, (
            f"Expected {expected} command(s), got {actual}"
        )

    def reset(self) -> None:
        self.commands_executed.clear()
        self.return_code = 0
