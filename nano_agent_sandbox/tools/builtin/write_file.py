"""
write_file.py — 文件写入工具
"""
from typing import Optional

from nano_agent_sandbox.sandbox.file_manager import FileManager

_file_mgr: Optional[FileManager] = None


def init(file_manager: FileManager):
    global _file_mgr
    _file_mgr = file_manager


def write_file(path: str, content: str) -> str:
    if _file_mgr is None:
        return "Error: File manager not initialized."
    try:
        return _file_mgr.write_file(path, content)
    except Exception as e:
        return f"Error: {e}"
