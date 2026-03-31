"""
read_file.py — 文件读取工具
"""
from typing import Optional

from nano_agent_sandbox.sandbox.file_manager import FileManager

_file_mgr: Optional[FileManager] = None


def init(file_manager: FileManager):
    global _file_mgr
    _file_mgr = file_manager


def read_file(path: str) -> str:
    if _file_mgr is None:
        return "Error: File manager not initialized."
    try:
        return _file_mgr.read_file(path)
    except Exception as e:
        return f"Error: {e}"
