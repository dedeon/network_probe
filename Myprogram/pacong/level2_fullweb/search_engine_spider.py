"""
第二级爬虫 - 搜索引擎全网搜索定制包
以第一级挖掘到的企业名称为输入，通过搜索引擎全网搜索定制安卓客户端
"""
import re
import time
import random
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PRODUCT_LINES, LEVEL2_SEARCH_TEMPLATES
from storage.db import AppInfoDB
from utils.search_engine import SearchEngineManager
from utils.html_parser import HTMLParser, extract_package_name_from_url
from utils.ua_pool import ua_pool
from utils.rate_limiter import rate_limiter
from utils.logger import get_logger
from level2_fullweb.result_analyzer import ResultAnalyzer

logger = get_logger('search_engine_spider')


class SearchEnginePackageSpider:
    """
    搜索引擎全网搜索定制包爬虫

    工作流程：
    1. 遍历客户名称列表
    2. 为每个客户名称构造搜索关键词（基于 LEVEL2_SEARCH_TEMPLATES）
    3. 通过搜索引擎搜索
    4. 分析搜索结果：分类URL，提取包名/应用名
    5. 对高价值结果页面进行二次爬取，提取更多应用信息
    6. 写入 app_info 表
    """

    # 二次爬取时从页面中提取包名的正则
    PAGE_PKG_PATTERNS = [
        re.compile(r'package[_\s]*(?:name)?[:\s=]*["\']?([a-zA-Z][a-zA-Z0-9_.]{4,})["\']?',
            re.IGNORECASE),
        re.compile(r'id=([a-zA-Z][a-zA-Z0-9_.]{4,})'),
        re.compile(r'packageName[:\s=]*["\']([a-zA-Z][a-zA-Z0-9_.]{4,})["\']'),
    ]

    def __init__(self, appinfo_db: Optional[AppInfoDB] = None,
                 customers: Optional[list[dict]] = None):
        self.db = appinfo_db or AppInfoDB()
        self.customers = customers or []
        self.analyzer = ResultAnalyzer()
        self.search_manager = SearchEngineManager()
        from utils.http_client import http_client
        self.http = http_client
        self.total_found = 0
        self._visited_urls: set[str] = set()

    def run(self):
        """执行搜索引擎全网定制包搜索"""
        logger.info(f"开始搜索引擎全网定制包搜索，共 {len(self.customers)} 个客户")

        if not self.customers:
            logger.warning("客户列表为空，跳过搜索引擎搜索")
            return

        for idx, customer in enumerate(self.customers):
            enterprise_name = customer.get('enterprise_name', '')
            product_line = customer.get('product_line', '')

            if not enterprise_name or not product_line:
                continue

            logger.info(
                f"[{idx + 1}/{len(self.customers)}] "
                f"搜索: {enterprise_name} ({product_line})"
            )

            try:
                self._search_for_customer(enterprise_name, product_line)
            except Exception as e:
                logger.error(f"搜索 {enterprise_name} 失败: {e}")

            # 客户之间的间隔
            time.sleep(random.uniform(1, 2))

        logger.info(f"搜索引擎搜索完成，共发现 {self.total_found} 个定制包候选")
        stats = self.db.get_stats()
        logger.info(f"应用库统计: {stats}")

    def _search_for_customer(self, enterprise_name: str, product_line: str):
        """针对单个客户搜索定制包"""
        # 构造搜索关键词
        keywords = self._build_search_keywords(enterprise_name, product_line)

        for keyword in keywords:
            try:
                # 搜索
                results = self.search_manager.search_with_dedup(
                    keyword, num_pages=1
                )
                if not results:
                    continue

                logger.debug(f"  关键词 '{keyword}' 获得 {len(results)} 条结果")

                # 分析搜索结果
                analyzed = self.analyzer.analyze_search_results(
                    results, enterprise_name, product_line
                )

                # 处理分析结果
                for item in analyzed:
                    if item['relevance_score'] < 0.05:
                        continue  # 跳过极低相关度结果

                    self._process_analyzed_result(
                        item, enterprise_name, product_line, keyword
                    )

            except Exception as e:
                logger.debug(f"  关键词 '{keyword}' 搜索失败: {e}")

            time.sleep(random.uniform(1, 2))

    def _build_search_keywords(self, enterprise_name: str,
                                product_line: str) -> list[str]:
        """构造搜索关键词"""
        keywords = []

        # 基于模板生成
        for template in LEVEL2_SEARCH_TEMPLATES:
            kw = template.replace('{enterprise}', enterprise_name)
            keywords.append(kw)

        # 已知App名的直接搜索
        known_app = None
        for customer in self.customers:
            if (customer.get('enterprise_name') == enterprise_name and
                    customer.get('known_app_name')):
                known_app = customer['known_app_name']
                break

        if known_app:
            keywords.insert(0, f'"{known_app}" 安卓 下载 apk')
            keywords.insert(0, f'"{known_app}" App Android')

        # 限制关键词数量，避免搜索量过大
        return keywords[:8]

    def _process_analyzed_result(self, item: dict, enterprise_name: str,
                                  product_line: str, keyword: str):
        """处理分析后的搜索结果"""
        url = item['url']
        result_type = item['type']

        # 1. 应用商店结果 → 直接记录
        if result_type == ResultAnalyzer.TYPE_APP_STORE:
            self._save_app_from_search(
                item, enterprise_name, product_line,
                discovery_method='搜索引擎→应用商店',
            )

        # 2. APK站结果 → 二次爬取提取详细信息
        elif result_type == ResultAnalyzer.TYPE_APK_SITE:
            if url not in self._visited_urls:
                self._visited_urls.add(url)
                self._crawl_and_extract(
                    url, enterprise_name, product_line,
                    discovery_method='搜索引擎→APK站',
                )

        # 3. 企业官网 / 政务门户 → 二次爬取
        elif result_type in (ResultAnalyzer.TYPE_ENTERPRISE_SITE,
                             ResultAnalyzer.TYPE_GOV_PORTAL):
            if url not in self._visited_urls:
                self._visited_urls.add(url)
                self._crawl_and_extract(
                    url, enterprise_name, product_line,
                    discovery_method=f'搜索引擎→{result_type}',
                )

        # 4. 直接从搜索结果中有足够信息的 → 记录
        elif item.get('package_name') and item.get('app_name'):
            self._save_app_from_search(
                item, enterprise_name, product_line,
                discovery_method='搜索引擎摘要',
            )

    def _save_app_from_search(self, item: dict, enterprise_name: str,
                               product_line: str,
                               discovery_method: str = '搜索引擎'):
        """从搜索结果中保存应用信息"""
        package_name = item.get('package_name', '')
        app_name = item.get('app_name', '')

        # 至少要有包名或应用名
        if not package_name and not app_name:
            return

        # 如果没有包名，使用应用名作为临时标识
        if not package_name:
            package_name = f"unknown.{app_name.replace(' ', '.')}"

        # 验证产品线
        matched_pl = item.get('product_line') or product_line
        if not matched_pl:
            return

        domain = item.get('domain', '')
        url = item.get('url', '')

        inserted = self.db.insert_app(
            package_name=package_name,
            app_name=app_name or enterprise_name,
            product_line=matched_pl,
            enterprise_name=enterprise_name,
            source_site=domain,
            source_url=url,
            discovery_method=discovery_method,
        )

        if inserted:
            self.total_found += 1
            logger.info(
                f"  发现: {app_name or package_name} | "
                f"{enterprise_name} | {matched_pl} | {domain}"
            )

    def _crawl_and_extract(self, url: str, enterprise_name: str,
                            product_line: str,
                            discovery_method: str = '搜索引擎→页面'):
        """二次爬取页面，提取应用信息"""
        try:
            domain = urlparse(url).netloc
        except Exception:
            domain = 'unknown'

        rate_limiter.wait(domain)

        html = self.http.get_text(url)
        if not html:
            logger.debug(f"  爬取失败 {url}")
            return

        parser = HTMLParser(html, url)

        # 1. 尝试从页面中提取应用信息
        page_info = parser.extract_app_info()

        # 2. 从页面文本中提取包名
        text = parser.get_text()
        page_packages = self._extract_packages_from_text(text)

        # 3. 查找下载链接
        download_links = parser.find_download_links()

        # 4. 从下载链接中提取包名
        for link in download_links:
            link_pkg = extract_package_name_from_url(link['url'])
            if link_pkg and link_pkg not in page_packages:
                page_packages.append(link_pkg)

        # 5. 保存发现的应用
        for pkg in page_packages:
            # 验证包名是否与目标产品线相关
            matched_pl = self.analyzer.match_product_line_for_package(pkg)
            if not matched_pl:
                # 包名不匹配任何产品线，检查文本上下文
                if not self._has_product_keyword_in_context(text, product_line):
                    continue
                matched_pl = product_line

            app_name = page_info.get('app_name', '')
            if not app_name:
                app_name = parser.get_title()

            inserted = self.db.insert_app(
                package_name=pkg,
                app_name=app_name,
                product_line=matched_pl,
                enterprise_name=enterprise_name,
                developer=page_info.get('developer', ''),
                version=page_info.get('version', ''),
                description=page_info.get('description', '')[:500],
                source_site=domain,
                source_url=url,
                discovery_method=discovery_method,
            )

            if inserted:
                self.total_found += 1
                logger.info(
                    f"  页面发现: {pkg} | {app_name} | "
                    f"{enterprise_name} | {domain}"
                )

    def _extract_packages_from_text(self, text: str) -> list[str]:
        """从页面文本中提取包名列表"""
        packages = []
        seen = set()

        for pattern in self.PAGE_PKG_PATTERNS:
            for match in pattern.finditer(text):
                pkg = match.group(1)
                if pkg not in seen and self._is_valid_package(pkg):
                    seen.add(pkg)
                    packages.append(pkg)

        return packages

    def _is_valid_package(self, name: str) -> bool:
        """验证包名有效性（排除域名）"""
        if not name or '.' not in name:
            return False
        parts = name.split('.')
        if len(parts) < 2:
            return False
        # 过滤常见非包名
        excluded_prefixes = [
            'www.', 'http.', 'com.cn', 'org.cn',
            'jquery.', 'lodash.', 'react.',
        ]
        for prefix in excluded_prefixes:
            if name.startswith(prefix):
                return False
        # 排除域名后缀
        domain_suffixes = ['.com', '.cn', '.org', '.net', '.gov', '.edu', '.io']
        for suffix in domain_suffixes:
            if name.endswith(suffix) or name.endswith(suffix.lstrip('.')):
                if not name.startswith('com.') and not name.startswith('org.') and not name.startswith('cn.'):
                    return False
        # 排除已知域名
        domain_patterns = ['qq.com', 'baidu.com', 'weixin.qq', 'sogou.com',
                          'bing.com', 'google.com', 'dldir1.qq', 'cdn.']
        for dp in domain_patterns:
            if dp in name:
                return False
        return True

    def _has_product_keyword_in_context(self, text: str,
                                         product_line: str) -> bool:
        """检查文本中是否包含产品线关键词"""
        pl_info = PRODUCT_LINES.get(product_line, {})
        for kw in pl_info.get('name_keywords', []):
            if kw in text:
                return True
        return False

    def close(self):
        self.search_manager.close()
