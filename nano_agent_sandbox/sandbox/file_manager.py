"""
file_manager.py — 沙箱文件系统管理

职责：
  1. 管理沙箱工作区目录
  2. 收集执行产物（图片、CSV 等）
  3. 提供安全的文件读写（路径沙箱化）
"""
import shutil
from pathlib import Path
from typing import List, Optional

from nano_agent_sandbox.config import SANDBOX_WORKDIR


class FileManager:
    """沙箱文件系统管理器"""

    # 允许收集的产物扩展名
    ARTIFACT_EXTENSIONS = {
        ".png", ".jpg", ".jpeg", ".gif", ".svg",   # 图片
        ".csv", ".json", ".txt", ".md",             # 数据/文档
        ".html", ".pdf",                            # 报告
    }

    def __init__(self, workdir: Optional[Path] = None):
        self.workdir = workdir or SANDBOX_WORKDIR
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.output_dir = self.workdir / "output"
        self.output_dir.mkdir(exist_ok=True)

    def safe_path(self, path_str: str) -> Path:
        """
        将相对路径解析为沙箱内的绝对路径。
        阻止路径逃逸（如 ../../etc/passwd）。
        """
        resolved = (self.workdir / path_str).resolve()
        if not resolved.is_relative_to(self.workdir):
            raise ValueError(f"Path escapes sandbox: {path_str}")
        return resolved

    def read_file(self, path_str: str) -> str:
        """安全地读取沙箱内文件"""
        fp = self.safe_path(path_str)
        if not fp.exists():
            raise FileNotFoundError(f"File not found: {path_str}")
        return fp.read_text(encoding="utf-8")[:50_000]

    def write_file(self, path_str: str, content: str) -> str:
        """安全地写入沙箱内文件"""
        fp = self.safe_path(path_str)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path_str}"

    def collect_artifacts(self) -> List[dict]:
        """
        收集沙箱中产出的文件（图片、数据文件等）。

        Returns:
            [{"name": "chart.png", "path": "/tmp/.../output/chart.png", "size": 12345}, ...]
        """
        artifacts = []
        for fp in self.workdir.rglob("*"):
            if fp.is_file() and fp.suffix.lower() in self.ARTIFACT_EXTENSIONS:
                artifacts.append({
                    "name": fp.name,
                    "path": str(fp),
                    "size": fp.stat().st_size,
                })
        return artifacts

    def cleanup(self):
        """清理整个沙箱工作目录"""
        if self.workdir.exists():
            shutil.rmtree(self.workdir, ignore_errors=True)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
