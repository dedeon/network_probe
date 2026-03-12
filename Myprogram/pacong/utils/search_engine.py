"""
搜索引擎封装模块
支持百度、必应、搜狗等免费搜索引擎的结果爬取
"""
import re
import time
import random
from typing import Optional
from urllib.parse import urlencode, quote_plus

from bs4 import BeautifulSoup

from utils.http_client import http_client
from utils.rate_limiter import rate_limiter
from utils.logger import get_logger

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SEARCH_ENGINES

logger = get_logger('search_engine')


class SearchResult:
    """搜索结果封装"""

    def __init__(self, title: str, url: str, snippet: str, source_engine: str):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.source_engine = source_engine

    def to_dict(self) -> dict:
        return {
            'title': self.title,
            'url': self.url,
            'snippet': self.snippet,
            'source_engine': self.source_engine,
        }

    def __repr__(self):
        return f"SearchResult(title='{self.title[:30]}...', url='{self.url}')"


class SearchEngine:
    """搜索引擎基类"""

    def __init__(self, engine_name: str):
        self.engine_name = engine_name
        self.config = SEARCH_ENGINES.get(engine_name, {})
        self.http = http_client
        # 注册搜索引擎限速
        delay = self.config.get('delay_range', (10, 15))
        rate_limiter.set_delay(engine_name, delay)
        if 'daily_limit' in self.config:
            rate_limiter.set_daily_limit(engine_name, self.config['daily_limit'])

    def search(self, keyword: str, num_pages: int = 3) -> list[SearchResult]:
        """执行搜索并返回结果列表"""
        raise NotImplementedError

    def _make_request(self, url: str, params: Optional[dict] = None) -> Optional[str]:
        """发送HTTP请求（通过统一客户端，自动重试和反爬处理）"""
        return self.http.get_text(
            url, params=params, domain_override=self.engine_name
        )

    def close(self):
        pass  # 使用全局http_client，不需要单独关闭


class BaiduSearch(SearchEngine):
    """百度搜索"""

    def __init__(self):
        super().__init__('baidu')

    def search(self, keyword: str, num_pages: int = 3) -> list[SearchResult]:
        results = []
        for page in range(num_pages):
            params = {
                'wd': keyword,
                'pn': page * 10,
                'rn': 10,
            }
            html = self._make_request(self.config['search_url'], params)
            if not html:
                break

            page_results = self._parse_results(html)
            results.extend(page_results)

            if len(page_results) < 5:
                break  # 结果不足，可能已到末尾

        logger.info(f"百度搜索 '{keyword}' 获得 {len(results)} 条结果")
        return results

    def _parse_results(self, html: str) -> list[SearchResult]:
        soup = BeautifulSoup(html, 'lxml')
        results = []

        for item in soup.select('.result, .c-container'):
            title_elem = item.select_one('h3 a, .t a')
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            url = title_elem.get('href', '')

            snippet_elem = item.select_one('.c-abstract, .content-right_8Zs40')
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''

            if title and url:
                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source_engine='baidu',
                ))
        return results


class BingSearch(SearchEngine):
    """必应搜索"""

    def __init__(self):
        super().__init__('bing')

    def search(self, keyword: str, num_pages: int = 3) -> list[SearchResult]:
        results = []
        for page in range(num_pages):
            params = {
                'q': keyword,
                'first': page * 10 + 1,
                'count': 10,
                'cc': 'cn',
            }
            html = self._make_request(self.config['search_url'], params)
            if not html:
                break

            page_results = self._parse_results(html)
            results.extend(page_results)

            if len(page_results) < 5:
                break

        logger.info(f"必应搜索 '{keyword}' 获得 {len(results)} 条结果")
        return results

    def _parse_results(self, html: str) -> list[SearchResult]:
        soup = BeautifulSoup(html, 'lxml')
        results = []

        for item in soup.select('.b_algo'):
            title_elem = item.select_one('h2 a')
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            url = title_elem.get('href', '')

            snippet_elem = item.select_one('.b_caption p')
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''

            if title and url:
                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source_engine='bing',
                ))
        return results


class SogouSearch(SearchEngine):
    """搜狗搜索"""

    def __init__(self):
        super().__init__('sogou')

    def search(self, keyword: str, num_pages: int = 3) -> list[SearchResult]:
        results = []
        for page in range(num_pages):
            params = {
                'query': keyword,
                'page': page + 1,
            }
            html = self._make_request(self.config['search_url'], params)
            if not html:
                break

            page_results = self._parse_results(html)
            results.extend(page_results)

            if len(page_results) < 5:
                break

        logger.info(f"搜狗搜索 '{keyword}' 获得 {len(results)} 条结果")
        return results

    def _parse_results(self, html: str) -> list[SearchResult]:
        soup = BeautifulSoup(html, 'lxml')
        results = []

        for item in soup.select('.vrwrap, .rb'):
            title_elem = item.select_one('h3 a, .vr-title a')
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            url = title_elem.get('href', '')

            snippet_elem = item.select_one('.star-wiki, .str-text-info')
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''

            if title and url:
                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source_engine='sogou',
                ))
        return results


class SearchEngineManager:
    """搜索引擎管理器 - 统一调度多个搜索引擎"""

    def __init__(self):
        self.engines: dict[str, SearchEngine] = {}
        self._init_engines()

    def _init_engines(self):
        engine_classes = {
            'baidu': BaiduSearch,
            'bing': BingSearch,
            'sogou': SogouSearch,
        }
        for name, cls in engine_classes.items():
            if name in SEARCH_ENGINES:
                try:
                    self.engines[name] = cls()
                except Exception as e:
                    logger.error(f"初始化搜索引擎 {name} 失败: {e}")

    def search(self, keyword: str, engines: Optional[list[str]] = None,
               num_pages: int = 3) -> list[SearchResult]:
        """
        使用指定的搜索引擎搜索
        Args:
            keyword: 搜索关键词
            engines: 指定使用的引擎列表，None则使用所有
            num_pages: 每个引擎搜索页数
        """
        target_engines = engines or list(self.engines.keys())
        all_results = []

        for engine_name in target_engines:
            engine = self.engines.get(engine_name)
            if not engine:
                continue
            try:
                results = engine.search(keyword, num_pages)
                all_results.extend(results)
            except Exception as e:
                logger.error(f"搜索引擎 {engine_name} 搜索失败: {e}")

        return all_results

    def search_with_dedup(self, keyword: str, engines: Optional[list[str]] = None,
                          num_pages: int = 3) -> list[SearchResult]:
        """搜索并按URL去重"""
        results = self.search(keyword, engines, num_pages)
        seen_urls = set()
        deduped = []
        for r in results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                deduped.append(r)
        return deduped

    def close(self):
        pass  # 使用全局http_client，无需单独关闭
