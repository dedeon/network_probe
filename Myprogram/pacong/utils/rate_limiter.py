"""
请求限速器 - 控制爬取频率，避免被封
"""
import asyncio
import random
import time
import threading
from collections import defaultdict
from typing import Optional

from utils.logger import get_logger

logger = get_logger('rate_limiter')


class RateLimiter:
    """
    基于域名的请求限速器
    支持同步和异步两种模式
    特性：自适应退避（域名被封时自动增加间隔）、域名暂停
    """

    def __init__(self, default_delay: tuple[float, float] = (3.0, 8.0)):
        """
        Args:
            default_delay: (min_seconds, max_seconds) 默认请求间隔范围
        """
        self.default_delay = default_delay
        self._domain_delays: dict[str, tuple[float, float]] = {}
        self._original_delays: dict[str, tuple[float, float]] = {}
        self._last_request: dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
        self._daily_counts: dict[str, int] = defaultdict(int)
        self._daily_limits: dict[str, int] = {}
        self._paused_domains: dict[str, float] = {}  # domain -> 暂停到的时间戳
        self._adaptive_multiplier: dict[str, float] = defaultdict(lambda: 1.0)

    def set_delay(self, domain: str, delay: tuple[float, float]):
        """为特定域名设置请求间隔"""
        self._domain_delays[domain] = delay
        if domain not in self._original_delays:
            self._original_delays[domain] = delay

    def set_daily_limit(self, domain: str, limit: int):
        """为特定域名设置每日请求上限"""
        self._daily_limits[domain] = limit

    def increase_delay(self, domain: str, factor: float = 2.0):
        """
        自适应增加域名延迟（被封时调用）
        Args:
            factor: 延迟倍增因子
        """
        self._adaptive_multiplier[domain] = min(
            self._adaptive_multiplier[domain] * factor, 10.0
        )
        logger.info(
            f"域名 {domain} 延迟倍率提升至 {self._adaptive_multiplier[domain]:.1f}x"
        )

    def reset_delay(self, domain: str):
        """重置域名延迟到原始值（请求成功后调用）"""
        if self._adaptive_multiplier[domain] > 1.0:
            # 逐步降低而非直接重置，避免震荡
            self._adaptive_multiplier[domain] = max(
                1.0, self._adaptive_multiplier[domain] * 0.7
            )

    def pause_domain(self, domain: str, seconds: float):
        """暂停某域名的请求"""
        self._paused_domains[domain] = time.time() + seconds
        logger.info(f"域名 {domain} 暂停 {seconds:.0f}s")

    def _is_paused(self, domain: str) -> bool:
        """检查域名是否处于暂停状态"""
        if domain in self._paused_domains:
            if time.time() < self._paused_domains[domain]:
                return True
            del self._paused_domains[domain]
        return False

    def _get_delay(self, domain: str) -> float:
        """获取域名的随机延迟时间（含自适应倍率）"""
        delay_range = self._domain_delays.get(domain, self.default_delay)
        base_delay = random.uniform(*delay_range)
        return base_delay * self._adaptive_multiplier[domain]

    def _check_daily_limit(self, domain: str) -> bool:
        """检查是否超过每日限制"""
        if domain not in self._daily_limits:
            return True
        return self._daily_counts[domain] < self._daily_limits[domain]

    def wait(self, domain: str) -> bool:
        """
        同步等待（阻塞直到可以发送请求）
        返回 False 表示超过每日限制或域名被暂停
        """
        with self._lock:
            # 检查暂停
            if self._is_paused(domain):
                remain = self._paused_domains.get(domain, 0) - time.time()
                if remain > 0:
                    logger.debug(f"域名 {domain} 暂停中，剩余 {remain:.0f}s")
                    time.sleep(remain)

            if not self._check_daily_limit(domain):
                logger.warning(f"域名 {domain} 已达每日请求上限 {self._daily_limits[domain]}")
                return False

            now = time.time()
            elapsed = now - self._last_request[domain]
            delay = self._get_delay(domain)

            if elapsed < delay:
                sleep_time = delay - elapsed
                logger.debug(f"限速等待 {sleep_time:.1f}s ({domain})")
                time.sleep(sleep_time)

            self._last_request[domain] = time.time()
            self._daily_counts[domain] += 1
            return True

    async def async_wait(self, domain: str) -> bool:
        """
        异步等待
        返回 False 表示超过每日限制
        """
        if self._is_paused(domain):
            remain = self._paused_domains.get(domain, 0) - time.time()
            if remain > 0:
                logger.debug(f"域名 {domain} 暂停中，剩余 {remain:.0f}s")
                await asyncio.sleep(remain)

        if not self._check_daily_limit(domain):
            logger.warning(f"域名 {domain} 已达每日请求上限 {self._daily_limits[domain]}")
            return False

        now = time.time()
        elapsed = now - self._last_request[domain]
        delay = self._get_delay(domain)

        if elapsed < delay:
            sleep_time = delay - elapsed
            logger.debug(f"限速等待 {sleep_time:.1f}s ({domain})")
            await asyncio.sleep(sleep_time)

        self._last_request[domain] = time.time()
        self._daily_counts[domain] += 1
        return True

    def reset_daily_counts(self):
        """重置每日计数"""
        self._daily_counts.clear()

    def get_stats(self) -> dict:
        """获取限速统计"""
        return {
            'daily_counts': dict(self._daily_counts),
            'daily_limits': dict(self._daily_limits),
            'adaptive_multipliers': {
                k: v for k, v in self._adaptive_multiplier.items()
                if v > 1.0
            },
            'paused_domains': list(self._paused_domains.keys()),
        }


# 全局限速器实例
rate_limiter = RateLimiter()
