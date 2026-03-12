"""
第三级爬虫 - 应用商店基础爬虫类
提供通用的HTTP请求、页面解析、结果存储等基础能力
"""
import re
import time
import random
from typing import Optional
from urllib.parse import urljoin, urlparse, quote_plus

import httpx
from bs4 import BeautifulSoup

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PRODUCT_LINES, APP_STORES, REQUEST_CONFIG
from storage.db import AppInfoDB
from utils.ua_pool import ua_pool
from utils.rate_limiter import rate_limiter
from utils.logger import get_logger

logger = get_logger('base_store_spider')


class BaseStoreSpider:
    """
    应用商店爬虫基类
    子类需实现:
      - search(keyword) -> list[dict]
      - parse_detail_page(url) -> dict
    """

    STORE_KEY = ''          # 商店标识，子类必须设置
    STORE_NAME = ''         # 商店中文名
    NEEDS_JS = False        # 是否需要JS渲染

    def __init__(self, appinfo_db: AppInfoDB):
        self.db = appinfo_db
        self.store_config = APP_STORES.get(self.STORE_KEY, {})
        self.client = httpx.Client(
            timeout=REQUEST_CONFIG.get('timeout', 30),
            follow_redirects=True,
            verify=False,
        )
        # 注册限速
        domain = self.store_config.get('domain', self.STORE_KEY)
        delay = REQUEST_CONFIG.get('default_delay', (3, 8))
        rate_limiter.set_delay(domain, delay)

    @property
    def domain(self) -> str:
        return self.store_config.get('domain', '')

    def search(self, keyword: str) -> list[dict]:
        """
        在商店内搜索关键词，返回结果列表
        Returns:
            [{'package_name', 'app_name', 'url', 'developer', ...}]
        子类必须实现
        """
        raise NotImplementedError

    def parse_detail_page(self, url: str) -> Optional[dict]:
        """
        解析应用详情页，提取完整信息
        Returns:
            {'package_name', 'app_name', 'developer', 'version',
             'download_count', 'description', 'update_date', ...}
        子类可选实现
        """
        return None

    def fetch_page(self, url: str, params: Optional[dict] = None,
                   headers: Optional[dict] = None) -> Optional[str]:
        """发送HTTP请求获取页面"""
        try:
            if not headers:
                headers = ua_pool.get_headers()
            rate_limiter.wait(self.domain)
            resp = self.client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.debug(f"fetch_page 失败 {url}: {e}")
            return None

    def fetch_json(self, url: str, params: Optional[dict] = None,
                   headers: Optional[dict] = None) -> Optional[dict]:
        """发送HTTP请求获取JSON"""
        try:
            if not headers:
                headers = ua_pool.get_headers()
            rate_limiter.wait(self.domain)
            resp = self.client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.debug(f"fetch_json 失败 {url}: {e}")
            return None

    def save_app(self, app_info: dict, discovery_method: str = '') -> bool:
        """保存应用信息到数据库"""
        if not app_info.get('package_name') or not app_info.get('app_name'):
            logger.debug(f"跳过不完整记录: {app_info}")
            return False

        # 匹配产品线
        product_line = app_info.get('product_line', '')
        if not product_line:
            product_line = self._match_product_line(
                app_info['package_name'], app_info['app_name']
            )

        if not product_line:
            logger.debug(f"无法匹配产品线，跳过: {app_info.get('app_name')}")
            return False

        return self.db.insert_app(
            package_name=app_info['package_name'],
            app_name=app_info['app_name'],
            product_line=product_line,
            enterprise_name=app_info.get('enterprise_name', ''),
            developer=app_info.get('developer', ''),
            version=app_info.get('version', ''),
            version_code=app_info.get('version_code', ''),
            update_date=app_info.get('update_date', ''),
            download_count=app_info.get('download_count', ''),
            description=app_info.get('description', '')[:500],
            source_site=self.STORE_NAME,
            source_url=app_info.get('url', ''),
            discovery_method=discovery_method or f'level3_{self.STORE_KEY}',
        )

    def _match_product_line(self, package_name: str, app_name: str) -> str:
        """通过包名和应用名匹配产品线"""
        # 先按包名匹配
        for pl_name, pl_info in PRODUCT_LINES.items():
            for pattern in pl_info['package_patterns']:
                if pattern.search(package_name):
                    return pl_name

        # 再按应用名关键词匹配
        app_name_lower = app_name.lower()
        for pl_name, pl_info in PRODUCT_LINES.items():
            for kw in pl_info['name_keywords']:
                if kw.lower() in app_name_lower:
                    return pl_name

        return ''

    def _is_custom_package(self, package_name: str) -> bool:
        """判断是否为定制包（非官方标准包）"""
        for pl_info in PRODUCT_LINES.values():
            official = pl_info.get('official_package', '')
            if package_name == official:
                return False
        return True

    def close(self):
        """关闭HTTP客户端"""
        self.client.close()
