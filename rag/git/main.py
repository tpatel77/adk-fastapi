from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse

app = FastAPI(title="Repo File Reader", version="1.0.0")

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_SUFFIXES: tuple[str, ...] = (".json", ".py", ".java")


def resolve_repo_path(relative_path: str) -> Path:
    safe_path = Path(relative_path)
    if safe_path.is_absolute():
        raise HTTPException(status_code=400, detail="Path must be relative to repo root.")
    resolved = (REPO_ROOT / safe_path).resolve()
    if not str(resolved).startswith(str(REPO_ROOT)):
        raise HTTPException(status_code=400, detail="Path escapes repo root.")
    return resolved


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/read", response_class=PlainTextResponse)
def read_file(
    path: str = Query(..., description="Path relative to repo root."),
    encoding: Literal["utf-8", "latin-1"] = Query("utf-8")
) -> str:
    resolved = resolve_repo_path(path)
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    if not resolved.is_file():
        raise HTTPException(status_code=400, detail="Path must point to a file.")
    if resolved.suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="File type not allowed.")
    try:
        return resolved.read_text(encoding=encoding)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Unable to decode file.") from exc
