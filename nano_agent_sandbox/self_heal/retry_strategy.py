"""
retry_strategy.py — 重试策略

职责：
  1. 判断错误是否可以重试
  2. 追踪重试次数，防止死循环
  3. 退避策略（连续重试相同错误时拒绝）
"""
from collections import defaultdict
from typing import Dict

from nano_agent_sandbox.config import MAX_RETRIES


class RetryStrategy:
    """重试策略管理器"""

    def __init__(self, max_retries: int = MAX_RETRIES):
        self.max_retries = max_retries
        # {error_type: attempt_count} — 追踪每种错误的重试次数
        self._attempts: Dict[str, int] = defaultdict(int)
        # 上一次错误的指纹（用于检测重复错误）
        self._last_error_fingerprint: str = ""

    def should_retry(self, error_info: dict) -> bool:
        """
        判断是否应该重试。

        拒绝重试的情况：
          1. 重试次数已耗尽
          2. 资源耗尽类错误（MemoryError 等，重试无意义）
          3. 连续 3 次完全相同的错误（说明 LLM 没学到教训）

        Args:
            error_info: ErrorAnalyzer.classify_error 返回的结构

        Returns:
            True = 可以重试，False = 放弃
        """
        error_type = error_info["type"]

        # 资源耗尽：重试没意义
        if error_type == "resource":
            return False

        # 检查全局重试次数
        total_attempts = sum(self._attempts.values())
        if total_attempts >= self.max_retries:
            return False

        # 检查相同错误类型的重试次数
        if self._attempts[error_type] >= self.max_retries:
            return False

        # 检查是否连续重复相同错误
        fingerprint = f"{error_info['error_name']}:{error_info['message'][:100]}"
        if fingerprint == self._last_error_fingerprint:
            # 连续相同错误，检查是否已重试太多次
            if self._attempts[error_type] >= 2:
                return False

        return True

    def record_attempt(self, error_info: dict):
        """记录一次重试尝试"""
        error_type = error_info["type"]
        self._attempts[error_type] += 1
        self._last_error_fingerprint = f"{error_info['error_name']}:{error_info['message'][:100]}"

    def retries_left(self, error_info: dict) -> int:
        """剩余可重试次数"""
        error_type = error_info["type"]
        return max(0, self.max_retries - self._attempts[error_type])

    def reset(self):
        """重置所有计数器（新任务开始时调用）"""
        self._attempts.clear()
        self._last_error_fingerprint = ""
