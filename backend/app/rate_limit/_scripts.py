from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent / "scripts"


def load(name: str) -> str:
    return (_SCRIPTS_DIR / name).read_text(encoding="utf-8")
