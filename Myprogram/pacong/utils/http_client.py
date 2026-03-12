"""
统一HTTP客户端 - 内置重试、指数退避、封禁检测、请求统计
所有爬虫模块应通过此客户端发送请求，确保反爬策略统一。
"""
import random
import time
import logging
from collections import defaultdict
from typing import Optional
from urllib.parse import urlparse

import httpx

from utils.ua_pool import ua_pool
from utils.rate_limiter import rate_limiter

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import REQUEST_CONFIG

logger = logging.getLogger('crawler.http_client')

# 被封禁的HTTP状态码
BLOCK_STATUS_CODES = {403, 429, 503, 418}

# 需要重试的HTTP状态码
RETRY_STATUS_CODES = {429, 500, 502, 503, 504, 408}


class RequestStats:
    """请求统计"""

    def __init__(self):
        self.total_requests = 0
        self.success_count = 0
        self.fail_count = 0
        self.retry_count = 0
        self.block_count = 0
        self.by_domain: dict[str, dict] = defaultdict(
            lambda: {'total': 0, 'success': 0, 'fail': 0, 'block': 0}
        )

    def record_success(self, domain: str):
        self.total_requests += 1
        self.success_count += 1
        self.by_domain[domain]['total'] += 1
        self.by_domain[domain]['success'] += 1

    def record_fail(self, domain: str):
        self.total_requests += 1
        self.fail_count += 1
        self.by_domain[domain]['total'] += 1
        self.by_domain[domain]['fail'] += 1

    def record_block(self, domain: str):
        self.block_count += 1
        self.by_domain[domain]['block'] += 1

    def record_retry(self):
        self.retry_count += 1

    def get_summary(self) -> dict:
        return {
            'total': self.total_requests,
            'success': self.success_count,
            'fail': self.fail_count,
            'retry': self.retry_count,
            'block': self.block_count,
            'success_rate': (
                f"{self.success_count / self.total_requests * 100:.1f}%"
                if self.total_requests else 'N/A'
            ),
            'by_domain': dict(self.by_domain),
        }


class BlockDetector:
    """
    封禁检测器
    根据连续失败/封禁响应判断是否被封，动态调整请求策略
    """

    def __init__(self):
        self._consecutive_blocks: dict[str, int] = defaultdict(int)
        self._blocked_domains: set[str] = set()
        # 连续被封N次则标记为封禁
        self.block_threshold = 3
        # 封禁后的冷却基数（秒）
        self.cooldown_base = 60

    def report_block(self, domain: str, status_code: int):
        """报告一次疑似封禁"""
        self._consecutive_blocks[domain] += 1
        count = self._consecutive_blocks[domain]

        if count >= self.block_threshold:
            self._blocked_domains.add(domain)
            cooldown = self.cooldown_base * (2 ** (count - self.block_threshold))
            cooldown = min(cooldown, 600)  # 最多10分钟
            logger.warning(
                f"域名 {domain} 疑似被封禁 (连续{count}次, HTTP {status_code}), "
                f"冷却 {cooldown:.0f}s"
            )
            time.sleep(cooldown)

    def report_success(self, domain: str):
        """报告成功请求，重置计数"""
        if domain in self._consecutive_blocks:
            self._consecutive_blocks[domain] = 0
        self._blocked_domains.discard(domain)

    def is_blocked(self, domain: str) -> bool:
        return domain in self._blocked_domains

    def get_blocked_domains(self) -> set[str]:
        return set(self._blocked_domains)


class HttpClient:
    """
    统一HTTP客户端

    特性：
    - 自动重试（指数退避 + 随机抖动）
    - 封禁检测与自适应冷却
    - 请求统计
    - UA轮换 + 请求头伪装
    - 域名级限速集成
    """

    def __init__(self, timeout: Optional[int] = None,
                 max_retries: Optional[int] = None,
                 retry_backoff: Optional[float] = None):
        self.timeout = timeout or REQUEST_CONFIG.get('timeout', 30)
        self.max_retries = max_retries or REQUEST_CONFIG.get('max_retries', 3)
        self.retry_backoff = retry_backoff or REQUEST_CONFIG.get('retry_backoff', 2)

        self.client = httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            verify=False,
        )
        self.stats = RequestStats()
        self.block_detector = BlockDetector()

    def get(self, url: str, params: Optional[dict] = None,
            headers: Optional[dict] = None,
            use_rate_limit: bool = True,
            domain_override: Optional[str] = None) -> Optional[httpx.Response]:
        """
        发送GET请求，自动重试和反爬处理

        Args:
            url: 请求URL
            params: 查询参数
            headers: 额外请求头（会与默认UA头合并）
            use_rate_limit: 是否使用限速器
            domain_override: 覆盖域名（用于限速和统计）
        Returns:
            httpx.Response 或 None（所有重试失败时）
        """
        domain = domain_override or self._extract_domain(url)

        # 检查域名是否被封禁
        if self.block_detector.is_blocked(domain):
            logger.debug(f"域名 {domain} 处于封禁状态，跳过请求")
            return None

        # 限速等待
        if use_rate_limit:
            if not rate_limiter.wait(domain):
                logger.warning(f"域名 {domain} 达到每日请求限制")
                return None

        # 构建请求头
        req_headers = ua_pool.get_headers()
        req_headers['Referer'] = self._generate_referer(url)
        if headers:
            req_headers.update(headers)

        # 重试循环
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.client.get(url, params=params, headers=req_headers)

                # 检查封禁状态码
                if resp.status_code in BLOCK_STATUS_CODES:
                    self.block_detector.report_block(domain, resp.status_code)
                    self.stats.record_block(domain)

                    if resp.status_code in RETRY_STATUS_CODES and attempt < self.max_retries:
                        self.stats.record_retry()
                        wait_time = self._calc_backoff(attempt, resp)
                        logger.debug(
                            f"HTTP {resp.status_code}, 第{attempt+1}次重试, "
                            f"等待 {wait_time:.1f}s ({url})"
                        )
                        time.sleep(wait_time)
                        # 重试时换UA
                        req_headers = ua_pool.get_headers()
                        req_headers['Referer'] = self._generate_referer(url)
                        if headers:
                            req_headers.update(headers)
                        continue
                    else:
                        self.stats.record_fail(domain)
                        logger.warning(
                            f"HTTP {resp.status_code} (封禁/限流), 放弃: {url}"
                        )
                        return None

                # 其他可重试状态码（5xx等）
                if resp.status_code in RETRY_STATUS_CODES and attempt < self.max_retries:
                    self.stats.record_retry()
                    wait_time = self._calc_backoff(attempt, resp)
                    logger.debug(
                        f"HTTP {resp.status_code}, 第{attempt+1}次重试, "
                        f"等待 {wait_time:.1f}s ({url})"
                    )
                    time.sleep(wait_time)
                    continue

                # 检查是否成功
                resp.raise_for_status()

                # 成功
                self.block_detector.report_success(domain)
                self.stats.record_success(domain)
                return resp

            except httpx.HTTPStatusError as e:
                last_error = e
                status = e.response.status_code

                if status in RETRY_STATUS_CODES and attempt < self.max_retries:
                    self.stats.record_retry()
                    wait_time = self._calc_backoff(attempt)
                    logger.debug(
                        f"HTTP {status}, 第{attempt+1}次重试, "
                        f"等待 {wait_time:.1f}s ({url})"
                    )
                    time.sleep(wait_time)
                    continue

                self.stats.record_fail(domain)
                logger.debug(f"HTTP错误 {status}: {url}")
                return None

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.max_retries:
                    self.stats.record_retry()
                    wait_time = self._calc_backoff(attempt)
                    logger.debug(
                        f"请求超时, 第{attempt+1}次重试, "
                        f"等待 {wait_time:.1f}s ({url})"
                    )
                    time.sleep(wait_time)
                    continue

                self.stats.record_fail(domain)
                logger.debug(f"请求超时（已重试{self.max_retries}次）: {url}")
                return None

            except httpx.RequestError as e:
                last_error = e
                if attempt < self.max_retries:
                    self.stats.record_retry()
                    wait_time = self._calc_backoff(attempt)
                    logger.debug(
                        f"请求错误, 第{attempt+1}次重试, "
                        f"等待 {wait_time:.1f}s ({url})"
                    )
                    time.sleep(wait_time)
                    continue

                self.stats.record_fail(domain)
                logger.debug(f"请求错误（已重试{self.max_retries}次）: {url} - {e}")
                return None

        # 所有重试用尽
        self.stats.record_fail(domain)
        logger.debug(f"请求最终失败: {url} - {last_error}")
        return None

    def get_text(self, url: str, **kwargs) -> Optional[str]:
        """发送GET请求并返回文本内容"""
        resp = self.get(url, **kwargs)
        if resp is not None:
            return resp.text
        return None

    def get_json(self, url: str, **kwargs) -> Optional[dict]:
        """发送GET请求并返回JSON"""
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        kwargs['headers']['Accept'] = 'application/json, text/plain, */*'

        resp = self.get(url, **kwargs)
        if resp is not None:
            try:
                return resp.json()
            except Exception as e:
                logger.debug(f"JSON解析失败: {url} - {e}")
        return None

    def _calc_backoff(self, attempt: int,
                      response: Optional[httpx.Response] = None) -> float:
        """
        计算退避等待时间
        支持 Retry-After 响应头
        """
        # 优先使用 Retry-After 头
        if response is not None:
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                try:
                    return float(retry_after) + random.uniform(1, 3)
                except ValueError:
                    pass

        # 指数退避 + 随机抖动
        base = self.retry_backoff ** attempt
        jitter = random.uniform(0.5, 1.5)
        return base * jitter

    def _extract_domain(self, url: str) -> str:
        """从URL提取域名"""
        try:
            return urlparse(url).netloc
        except Exception:
            return 'unknown'

    def _generate_referer(self, url: str) -> str:
        """生成合理的Referer"""
        try:
            parsed = urlparse(url)
            # 使用域名首页作为Referer
            return f"{parsed.scheme}://{parsed.netloc}/"
        except Exception:
            return 'https://www.baidu.com/'

    def get_stats(self) -> dict:
        """获取请求统计"""
        stats = self.stats.get_summary()
        stats['blocked_domains'] = list(self.block_detector.get_blocked_domains())
        return stats

    def print_stats(self):
        """打印请求统计"""
        s = self.stats
        print(f"\n{'='*50}")
        print(f"  HTTP请求统计")
        print(f"{'='*50}")
        print(f"  总请求数: {s.total_requests}")
        print(f"  成功:     {s.success_count}")
        print(f"  失败:     {s.fail_count}")
        print(f"  重试:     {s.retry_count}")
        print(f"  封禁:     {s.block_count}")
        if s.total_requests:
            rate = s.success_count / s.total_requests * 100
            print(f"  成功率:   {rate:.1f}%")
        blocked = self.block_detector.get_blocked_domains()
        if blocked:
            print(f"  被封域名: {', '.join(blocked)}")
        print(f"{'='*50}\n")

    def close(self):
        """关闭客户端"""
        self.client.close()


# 全局单例
http_client = HttpClient()
