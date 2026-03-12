"""
第二级爬虫 - 企业官网下载页扫描
对搜索到的企业官网进行深度扫描，寻找App下载入口和定制包信息
"""
import re
import time
import random
from typing import Optional
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    PRODUCT_LINES, ENTERPRISE_DOWNLOAD_PATHS,
    ENTERPRISE_DOWNLOAD_KEYWORDS,
)
from storage.db import AppInfoDB
from utils.search_engine import SearchEngineManager
from utils.html_parser import HTMLParser, extract_package_name_from_url
from utils.ua_pool import ua_pool
from utils.rate_limiter import rate_limiter
from utils.logger import get_logger
from level2_fullweb.result_analyzer import ResultAnalyzer

logger = get_logger('enterprise_site_spider')


class EnterpriseSiteSpider:
    """
    企业官网下载页扫描爬虫

    工作流程：
    1. 通过搜索引擎搜索企业官网
    2. 探测企业官网常见下载路径（/download, /app, /mobile 等）
    3. 在找到的页面中提取App下载链接和应用信息
    4. 解析下载链接中的APK包名
    5. 写入 app_info 表
    """

    # 从APK文件名中提取包名的正则
    APK_FILENAME_PATTERNS = [
        re.compile(r'([a-zA-Z][a-zA-Z0-9_.]{4,})\.apk', re.IGNORECASE),
        re.compile(r'([a-zA-Z][a-zA-Z0-9_.]{4,})[-_]v?\d', re.IGNORECASE),
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
        self._scanned_domains: set[str] = set()

    def run(self):
        """执行企业官网扫描"""
        logger.info(f"开始企业官网下载页扫描，共 {len(self.customers)} 个客户")

        if not self.customers:
            logger.warning("客户列表为空，跳过企业官网扫描")
            return

        # 按企业名去重（同一企业可能对应多个产品线）
        unique_enterprises = {}
        for c in self.customers:
            name = c.get('enterprise_name', '')
            if name and name not in unique_enterprises:
                unique_enterprises[name] = c

        logger.info(f"去重后 {len(unique_enterprises)} 个独立企业")

        for idx, (name, customer) in enumerate(unique_enterprises.items()):
            product_line = customer.get('product_line', '')

            logger.info(
                f"[{idx + 1}/{len(unique_enterprises)}] "
                f"扫描: {name}"
            )

            try:
                self._scan_enterprise(name, product_line)
            except Exception as e:
                logger.error(f"扫描 {name} 失败: {e}")

            time.sleep(random.uniform(1, 2))

        logger.info(f"企业官网扫描完成，共发现 {self.total_found} 个定制包候选")

    def _scan_enterprise(self, enterprise_name: str, product_line: str):
        """扫描单个企业的官网"""
        # 1. 搜索企业官网
        official_url = self._find_official_site(enterprise_name)
        if not official_url:
            logger.debug(f"  未找到 {enterprise_name} 的官网")
            return

        domain = urlparse(official_url).netloc
        if domain in self._scanned_domains:
            logger.debug(f"  {domain} 已扫描过，跳过")
            return
        self._scanned_domains.add(domain)

        logger.info(f"  官网: {official_url}")

        # 2. 爬取官网首页，收集导航链接
        homepage_links = self._get_homepage_links(official_url)

        # 3. 探测常见下载路径
        download_pages = self._probe_download_paths(official_url)

        # 4. 从首页链接中寻找下载相关链接
        for link in homepage_links:
            if self._is_download_related(link):
                if link['url'] not in [p['url'] for p in download_pages]:
                    download_pages.append(link)

        logger.info(f"  发现 {len(download_pages)} 个下载相关页面")

        # 5. 爬取每个下载页面，提取App信息
        for page in download_pages[:10]:  # 限制每个企业最多扫描10个下载页
            try:
                self._extract_from_download_page(
                    page['url'], enterprise_name, product_line, domain
                )
            except Exception as e:
                logger.debug(f"  提取下载页失败 {page['url']}: {e}")
            time.sleep(random.uniform(1, 3))

    def _find_official_site(self, enterprise_name: str) -> Optional[str]:
        """通过搜索引擎查找企业官网"""
        keyword = f'"{enterprise_name}" 官网'

        results = self.search_manager.search_with_dedup(
            keyword, engines=['baidu'], num_pages=1
        )

        for r in results:
            url = r.url
            try:
                domain = urlparse(url).netloc.lower()
            except Exception:
                continue

            # 排除搜索引擎、社交媒体等非企业官网域名
            excluded = [
                'baidu.com', 'bing.com', 'sogou.com', 'google.com',
                'zhihu.com', '36kr.com', 'sohu.com', '163.com',
                'sina.com.cn', 'qq.com', 'weibo.com',
                'csdn.net', 'jianshu.com', 'bilibili.com',
                'wikipedia.org', 'baike.baidu.com',
                'douyin.com', 'tiktok.com',
            ]
            is_excluded = False
            for exc_domain in excluded:
                if exc_domain in domain:
                    is_excluded = True
                    break

            if not is_excluded:
                # 基本验证：返回第一个非排除域名的结果
                parsed = urlparse(url)
                return f"{parsed.scheme}://{parsed.netloc}"

        return None

    def _get_homepage_links(self, base_url: str) -> list[dict]:
        """获取首页中的链接"""
        rate_limiter.wait(urlparse(base_url).netloc)
        headers = ua_pool.get_headers()

        try:
            response = self.http.get(base_url, headers=headers)
            if response is None:
                return []
            response.raise_for_status()
            html = response.text
        except Exception as e:
            logger.debug(f"  获取首页失败 {base_url}: {e}")
            return []

        parser = HTMLParser(html, base_url)
        all_links = parser.get_links()

        # 过滤只保留同域链接
        domain = urlparse(base_url).netloc
        same_domain_links = []
        for link in all_links:
            try:
                link_domain = urlparse(link['url']).netloc
                if domain in link_domain or link_domain in domain:
                    same_domain_links.append(link)
            except Exception:
                continue

        return same_domain_links

    def _probe_download_paths(self, base_url: str) -> list[dict]:
        """探测常见下载路径"""
        download_pages = []
        domain = urlparse(base_url).netloc

        for path in ENTERPRISE_DOWNLOAD_PATHS:
            url = urljoin(base_url, path)

            resp = self.http.get(url)
            if resp is not None and resp.status_code == 200:
                # 检查页面是否包含下载关键词
                text = resp.text.lower()
                has_download_content = any(
                    kw.lower() in text
                    for kw in ENTERPRISE_DOWNLOAD_KEYWORDS
                )
                if has_download_content:
                    download_pages.append({
                        'url': url,
                        'text': f'探测路径 {path}',
                        'html': resp.text,
                    })
                    logger.debug(f"  探测命中: {url}")

            time.sleep(random.uniform(0.5, 1.5))

        return download_pages

    def _is_download_related(self, link: dict) -> bool:
        """判断链接是否与下载相关"""
        url = link.get('url', '').lower()
        text = link.get('text', '').lower()
        combined = f"{url} {text}"

        download_indicators = [
            '下载', 'download', 'app', 'android', '安卓',
            '移动', 'mobile', 'client', '客户端',
            'apk', '手机',
        ]

        for indicator in download_indicators:
            if indicator in combined:
                return True

        return False

    def _extract_from_download_page(self, url: str, enterprise_name: str,
                                     product_line: str, domain: str):
        """从下载页面中提取应用信息"""
        # 检查是否已有缓存的HTML
        html = None
        if isinstance(url, dict) and 'html' in url:
            html = url['html']
            url = url['url']

        if not html:
            html = self.http.get_text(url)
            if not html:
                logger.debug(f"  爬取下载页失败 {url}")
                return

        parser = HTMLParser(html, url)

        # 1. 查找下载链接
        download_links = parser.find_download_links()

        # 2. 从页面提取应用信息
        page_info = parser.extract_app_info()

        # 3. 搜索页面文本中的关键信息
        text = parser.get_text()

        # 4. 处理每个下载链接
        for dl_link in download_links:
            link_url = dl_link['url']
            link_type = dl_link['type']

            # 提取包名
            package_name = extract_package_name_from_url(link_url)
            if not package_name:
                package_name = self._extract_package_from_filename(link_url)

            if not package_name:
                continue

            # 验证是否与目标产品线相关
            matched_pl = self.analyzer.match_product_line_for_package(package_name)
            if not matched_pl:
                # 包名不直接匹配，检查页面上下文
                pl_info = PRODUCT_LINES.get(product_line, {})
                has_keyword = any(kw in text for kw in pl_info.get('name_keywords', []))
                if has_keyword:
                    matched_pl = product_line
                else:
                    continue

            # 确定应用名
            app_name = page_info.get('app_name', '') or dl_link.get('text', '')
            if not app_name:
                app_name = parser.get_title()

            inserted = self.db.insert_app(
                package_name=package_name,
                app_name=app_name,
                product_line=matched_pl,
                enterprise_name=enterprise_name,
                developer=page_info.get('developer', ''),
                version=page_info.get('version', ''),
                description=page_info.get('description', '')[:500],
                source_site=domain,
                source_url=url,
                discovery_method='企业官网扫描',
            )

            if inserted:
                self.total_found += 1
                logger.info(
                    f"  官网发现: {package_name} | {app_name} | "
                    f"{enterprise_name} | {domain}"
                )

        # 5. 检查是否有应用商店链接
        all_links = parser.get_links()
        for link in all_links:
            link_info = self.analyzer.classify_url(link['url'])
            if link_info['type'] == ResultAnalyzer.TYPE_APP_STORE:
                pkg = link_info.get('package_name') or extract_package_name_from_url(link['url'])
                if pkg:
                    matched_pl = self.analyzer.match_product_line_for_package(pkg)
                    if matched_pl:
                        inserted = self.db.insert_app(
                            package_name=pkg,
                            app_name=link.get('text', '') or enterprise_name,
                            product_line=matched_pl,
                            enterprise_name=enterprise_name,
                            source_site=link_info['domain'],
                            source_url=link['url'],
                            discovery_method='企业官网→应用商店',
                        )
                        if inserted:
                            self.total_found += 1
                            logger.info(
                                f"  官网商店链接: {pkg} | "
                                f"{enterprise_name} | {link_info['domain']}"
                            )

    def _extract_package_from_filename(self, url: str) -> Optional[str]:
        """从URL中APK文件名提取包名"""
        for pattern in self.APK_FILENAME_PATTERNS:
            match = pattern.search(url)
            if match:
                pkg = match.group(1)
                if '.' in pkg and len(pkg) >= 5:
                    return pkg
        return None

    def close(self):
        self.search_manager.close()
