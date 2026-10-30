"""Shared data models for CodeLens."""
from dataclasses import dataclass, field
from typing import List


@dataclass
class Chunk:
    """Represents a code chunk (function, method, class, or module) extracted from a repository."""
    id: str            # "C1", "C2"... assigned at index time
    file_path: str     # relative to repo root
    symbol: str        # function/class/method name, or "<module>"
    kind: str          # "function" | "class" | "method" | "module"
    start_line: int
    end_line: int
    signature: str
    docstring: str
    code: str
    imports: List[str]
    calls: List[str]   # function names called inside this chunk
    language: str
