"""Persistent tool store — saves/loads agent-created tools as JSON files."""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

from .. import config


@dataclass
class ToolRecord:
    name: str
    description: str
    code: str
    schema: dict
    test_cases: List[dict] = field(default_factory=list)
    version: int = 1
    created_by: str = "agent"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ToolRecord":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class ToolStore:
    """File-based persistent storage for agent-created tools."""

    def __init__(self, store_dir: Optional[Path] = None):
        self.store_dir = store_dir or config.TOOL_STORE_DIR
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def save(self, record: ToolRecord) -> Path:
        path = self.store_dir / f"{record.name}.json"
        path.write_text(
            json.dumps(record.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def load(self, name: str) -> Optional[ToolRecord]:
        path = self.store_dir / f"{name}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return ToolRecord.from_dict(data)

    def load_all(self) -> List[ToolRecord]:
        records = []
        for path in sorted(self.store_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                records.append(ToolRecord.from_dict(data))
            except Exception:
                continue
        return records

    def delete(self, name: str) -> bool:
        path = self.store_dir / f"{name}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def exists(self, name: str) -> bool:
        return (self.store_dir / f"{name}.json").exists()
