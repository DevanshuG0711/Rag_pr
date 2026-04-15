import json
from pathlib import Path


_STATE_FILE = Path("data/context_state.json")
_uploaded_file_name: str | None = None
_repo_indexed: bool = False


def _load_state() -> None:
    global _uploaded_file_name, _repo_indexed

    if not _STATE_FILE.exists():
        return

    try:
        data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return

    file_name = str(data.get("uploaded_file_name") or "").strip()
    _uploaded_file_name = file_name or None
    _repo_indexed = bool(data.get("repo_indexed", False))


def _save_state() -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(
        json.dumps(
            {
                "uploaded_file_name": _uploaded_file_name,
                "repo_indexed": _repo_indexed,
            }
        ),
        encoding="utf-8",
    )


def set_uploaded_file(file_name: str | None) -> None:
    global _uploaded_file_name
    normalized = str(file_name or "").strip()
    _uploaded_file_name = normalized or None
    _save_state()


def get_uploaded_file_name() -> str | None:
    if _uploaded_file_name is None:
        _load_state()
    return _uploaded_file_name


def set_repo_indexed(value: bool) -> None:
    global _repo_indexed
    _repo_indexed = bool(value)
    _save_state()


def is_repo_indexed() -> bool:
    if not _repo_indexed:
        _load_state()
    return _repo_indexed


def get_context_mode() -> str:
    if _uploaded_file_name:
        return "file_only"
    if _repo_indexed:
        return "global"
    return "global"
