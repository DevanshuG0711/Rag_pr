_uploaded_file_name: str | None = None
_repo_indexed: bool = False


def set_uploaded_file(file_name: str | None) -> None:
    global _uploaded_file_name
    normalized = str(file_name or "").strip()
    _uploaded_file_name = normalized or None


def get_uploaded_file_name() -> str | None:
    return _uploaded_file_name


def set_repo_indexed(value: bool) -> None:
    global _repo_indexed
    _repo_indexed = bool(value)


def is_repo_indexed() -> bool:
    return _repo_indexed


def get_context_mode() -> str:
    if _uploaded_file_name:
        return "file_only"
    if _repo_indexed:
        return "global"
    return "global"
