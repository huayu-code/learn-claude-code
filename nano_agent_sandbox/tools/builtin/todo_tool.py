"""
todo_tool.py — 任务追踪工具（借鉴 learn-claude-code s03）

让 Agent 自主管理任务进度，同一时刻只允许 1 个 in_progress。
"""
from typing import List


class TodoManager:
    """结构化任务管理器"""

    def __init__(self):
        self.items: List[dict] = []

    def update(self, items: list) -> str:
        """
        全量更新任务列表。

        校验规则：
          - 最多 20 条
          - text 不能为空
          - status 只能是 pending / in_progress / completed
          - 同一时刻最多 1 个 in_progress（强制顺序聚焦）
        """
        if len(items) > 20:
            raise ValueError("Max 20 todos allowed.")
        validated = []
        in_progress_count = 0
        for i, item in enumerate(items):
            text = str(item.get("text", "")).strip()
            status = str(item.get("status", "pending")).lower()
            item_id = str(item.get("id", str(i + 1)))
            if not text:
                raise ValueError(f"Item {item_id}: text required.")
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Item {item_id}: invalid status '{status}'.")
            if status == "in_progress":
                in_progress_count += 1
            validated.append({"id": item_id, "text": text, "status": status})
        if in_progress_count > 1:
            raise ValueError("Only one task can be in_progress at a time.")
        self.items = validated
        return self.render()

    def render(self) -> str:
        """渲染成可读清单"""
        if not self.items:
            return "No todos."
        lines = []
        for item in self.items:
            marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}[item["status"]]
            lines.append(f"{marker} #{item['id']}: {item['text']}")
        done = sum(1 for t in self.items if t["status"] == "completed")
        lines.append(f"\n({done}/{len(self.items)} completed)")
        return "\n".join(lines)


# 全局单例
TODO = TodoManager()


def todo(items: list) -> str:
    """工具入口函数"""
    return TODO.update(items)
