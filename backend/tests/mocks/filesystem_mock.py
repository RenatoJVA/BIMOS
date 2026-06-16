import json
from pathlib import Path
from typing import Any


class FilesystemMock:
    def __init__(self, base_path: Path | None = None):
        self.base_path = base_path or Path("/tmp/bimos_test_fs")
        self.files: dict[str, str] = {}
        self.dirs: set[str] = set()

    def mkdir(self, path: str | Path, parents: bool = False, exist_ok: bool = False) -> None:
        p = str(path)
        self.dirs.add(p)
        if parents:
            parent = Path(p).parent
            while str(parent) != str(parent.anchor):
                self.dirs.add(str(parent))
                parent = parent.parent

    def write_text(self, path: str | Path, content: str) -> None:
        self.files[str(path)] = content
        self.mkdir(Path(path).parent, parents=True, exist_ok=True)

    def read_text(self, path: str | Path) -> str:
        p = str(path)
        if p not in self.files:
            raise FileNotFoundError(f"File not found: {p}")
        return self.files[p]

    def exists(self, path: str | Path) -> bool:
        return str(path) in self.files or str(path) in self.dirs

    def unlink(self, path: str | Path, missing_ok: bool = False) -> None:
        p = str(path)
        if p in self.files:
            del self.files[p]
        elif p in self.dirs:
            self.dirs.discard(p)
        elif not missing_ok:
            raise FileNotFoundError(f"Path not found: {p}")

    def glob(self, pattern: str) -> list[str]:
        return [p for p in self.files if Path(p).match(pattern)]

    def write_json(self, path: str | Path, data: Any) -> None:
        self.write_text(path, json.dumps(data, indent=2))

    def read_json(self, path: str | Path) -> Any:
        return json.loads(self.read_text(path))

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def dir_count(self) -> int:
        return len(self.dirs)

    def clear(self) -> None:
        self.files.clear()
        self.dirs.clear()
