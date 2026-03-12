"""
第二级爬虫 - APK收录站爬虫
从第三方APK收录站（APKPure/酷安/安智/PP助手等）爬取定制包信息
"""
import re
import time
import random
from typing import Optional
from urllib.parse import urlparse, urljoin, quote

import httpx
from bs4 import BeautifulSoup

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PRODUCT_LINES, STORE_SEARCH_KEYWORDS
from storage.db import AppInfoDB
from utils.html_parser import HTMLParser, extract_package_name_from_url
from utils.ua_pool import ua_pool
from utils.rate_limiter import rate_limiter
from utils.logger import get_logger
from level2_fullweb.result_analyzer import ResultAnalyzer

logger = get_logger('apk_site_spider')


class APKSiteSpider:
    """
    APK收录站爬虫

    支持的站点：
    - APKPure: apkpure.com
    - 酷安: coolapk.com
    - 安智市场: anzhi.com
    - PP助手: pp.cn
    - 历趣: liqucn.com
    - AppChina: appchina.com

    工作流程：
    1. 使用产品关键词在各APK站内搜索
    2. 解析搜索结果列表页
    3. 进入详情页提取完整应用信息
    4. 验证是否为目标产品线的定制包
    5. 写入 app_info 表
    """

    # 各APK站点的搜索和解析配置
    SITE_CONFIGS = {
        'apkpure': {
            'name': 'APKPure',
            'domain': 'apkpure.com',
            'search_url': 'https://apkpure.com/cn/search?q={keyword}',
            'result_selector': '.search-title a',
            'detail_selectors': {
                'app_name': '.detail-title .app-name, h1.app-title',
                'package_name': '.detail-sdk-info .info-content, .apk-info .info',
                'developer': '.detail-developer .info-content, .developer-info a',
                'version': '.detail-version .info-content, .version-info',
                'description': '.description .content, .detail-description',
                'download_count': '.detail-download .info-content',
                'update_date': '.detail-update .info-content, .update-time',
            },
            'needs_js': False,
        },
        'coolapk': {
            'name': '酷安',
            'domain': 'www.coolapk.com',
            'search_url': 'https://www.coolapk.com/search?q={keyword}',
            'result_selector': '.app-list a.app-title, .list_app_info a',
            'detail_selectors': {
                'app_name': '.detail_app_title, h1',
                'package_name': '.apk_topba_message .apk_left_title_info',
                'developer': '.detail_app_developer, .app-info-developer',
                'version': '.list_app_info, .apk_topba_message',
                'description': '.apk_left_title_info_des, .app_description',
                'download_count': '.list_app_info, .detail_down_num',
                'update_date': '.apk_topba_message, .app-info-update',
            },
            'needs_js': True,
        },
        'wandoujia': {
            'name': '豌豆荚',
            'domain': 'www.wandoujia.com',
            'search_url': 'https://www.wandoujia.com/search?key={keyword}',
            'result_selector': '.search-result-list .app-title-h2 a, .card a.name',
            'detail_selectors': {
                'app_name': '.app-name span, h1.app-name',
                'package_name': '.infos-list .info-val, .app-info .info',
                'developer': '.dev-name, .infos-list .info-val',
                'version': '.infos-list .info-val, .app-info .version',
                'description': '.desc-info .content, .app-desc',
                'download_count': '.num-list .item .num, .install-count',
                'update_date': '.infos-list .info-val, .update-date',
            },
            'needs_js': False,
        },
        'anzhi': {
            'name': '安智市场',
            'domain': 'www.anzhi.com',
            'search_url': 'https://www.anzhi.com/search.php?keyword={keyword}',
            'result_selector': '.app_list .app_name a, .app-list-item a.name',
            'detail_selectors': {
                'app_name': '.detail_head .app_name, h1',
                'package_name': '.app_detail .detail_info',
                'developer': '.detail_info .developer',
                'version': '.detail_info .version, .app_detail .ver',
                'description': '.app_detail_desc, .detail-desc',
                'download_count': '.detail_info .down_num',
                'update_date': '.detail_info .update_date',
            },
            'needs_js': False,
        },
    }

    def __init__(self, appinfo_db: Optional[AppInfoDB] = None):
        self.db = appinfo_db or AppInfoDB()
        self.analyzer = ResultAnalyzer()
        from utils.http_client import http_client
        self.http = http_client
        self.total_found = 0
        self._visited_urls: set[str] = set()

    def run(self):
        """执行APK站点搜索"""
        logger.info("开始APK收录站爬取...")

        for site_key, site_config in self.SITE_CONFIGS.items():
            if site_config.get('needs_js'):
                logger.info(f"  跳过 {site_config['name']}（需要JS渲染）")
                continue

            logger.info(f"--- 站点: {site_config['name']} ---")

            for keyword in STORE_SEARCH_KEYWORDS:
                try:
                    self._search_site(site_key, site_config, keyword)
                except Exception as e:
                    logger.error(f"  搜索 {site_config['name']} '{keyword}' 失败: {e}")

                time.sleep(random.uniform(3, 6))

        logger.info(f"APK收录站爬取完成，共发现 {self.total_found} 个应用")

    def _search_site(self, site_key: str, config: dict, keyword: str):
        """在指定APK站中搜索"""
        search_url = config['search_url'].replace('{keyword}', quote(keyword))
        domain = config['domain']

        rate_limiter.wait(domain)

        html = self.http.get_text(search_url)
        if not html:
            logger.debug(f"  搜索请求失败 {search_url}")
            return

        # 解析搜索结果列表
        soup = BeautifulSoup(html, 'lxml')
        result_links = soup.select(config['result_selector'])

        logger.debug(f"  '{keyword}' 在 {config['name']} 找到 {len(result_links)} 条结果")

        for link_elem in result_links[:20]:  # 限制每个关键词最多处理20条
            href = link_elem.get('href', '')
            if not href:
                continue

            detail_url = urljoin(search_url, href)
            if detail_url in self._visited_urls:
                continue
            self._visited_urls.add(detail_url)

            link_text = link_elem.get_text(strip=True)

            # 初步判断是否可能是目标应用
            if not self._is_potential_target(link_text, href):
                continue

            try:
                self._crawl_detail_page(
                    detail_url, config, domain, keyword
                )
            except Exception as e:
                logger.debug(f"  详情页爬取失败 {detail_url}: {e}")

            time.sleep(random.uniform(2, 4))

    def _crawl_detail_page(self, url: str, config: dict,
                           domain: str, keyword: str):
        """爬取应用详情页"""
        rate_limiter.wait(domain)

        html = self.http.get_text(url)
        if not html:
            logger.debug(f"  详情页请求失败 {url}")
            return

        soup = BeautifulSoup(html, 'lxml')
        selectors = config['detail_selectors']

        # 提取应用信息
        app_info = {}
        for field, selector in selectors.items():
            value = self._safe_select_text(soup, selector)
            if value:
                app_info[field] = value

        # 从URL中提取包名
        url_pkg = extract_package_name_from_url(url)
        if url_pkg:
            app_info['package_name'] = url_pkg

        # 从页面文本中查找包名
        if not app_info.get('package_name'):
            text = soup.get_text()
            pkg_match = re.search(
                r'([a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9]*){2,})',
                text
            )
            if pkg_match:
                pkg = pkg_match.group(1)
                if self._is_valid_package(pkg):
                    app_info['package_name'] = pkg

        # 必须有包名才能存储
        package_name = app_info.get('package_name', '')
        if not package_name:
            return

        # 匹配产品线
        app_name = app_info.get('app_name', '')
        combined = f"{package_name} {app_name}"
        product_line = self.analyzer.match_product_line_for_package(package_name)

        if not product_line:
            product_line = self._match_product_by_name(app_name)

        if not product_line:
            # 从搜索关键词反推产品线
            product_line = self._match_product_by_keyword(keyword)

        if not product_line:
            return

        # 提取企业名
        enterprise_name = self._extract_enterprise_name(app_name, product_line)

        # 存储
        inserted = self.db.insert_app(
            package_name=package_name,
            app_name=app_name,
            product_line=product_line,
            enterprise_name=enterprise_name or '',
            developer=app_info.get('developer', ''),
            version=app_info.get('version', ''),
            download_count=app_info.get('download_count', ''),
            update_date=app_info.get('update_date', ''),
            description=app_info.get('description', '')[:500],
            source_site=domain,
            source_url=url,
            discovery_method='APK站搜索',
        )

        if inserted:
            self.total_found += 1
            logger.info(
                f"  APK站发现: {package_name} | {app_name} | "
                f"{product_line} | {domain}"
            )

    def _safe_select_text(self, soup: BeautifulSoup, selector: str) -> str:
        """安全地从多个CSS选择器中提取文本"""
        for sel in selector.split(','):
            sel = sel.strip()
            try:
                elem = soup.select_one(sel)
                if elem:
                    text = elem.get_text(strip=True)
                    if text:
                        return text[:200]  # 限制长度
            except Exception:
                continue
        return ''

    def _is_potential_target(self, text: str, href: str) -> bool:
        """初步判断是否可能是目标应用"""
        combined = f"{text} {href}".lower()

        for pl_info in PRODUCT_LINES.values():
            for kw in pl_info['name_keywords']:
                if kw.lower() in combined:
                    return True
            for pattern in pl_info['package_patterns']:
                if pattern.search(combined):
                    return True

        # 通用关键词
        generic_keywords = [
            '政务', '办公', 'oa', '移动', '协同',
        ]
        for kw in generic_keywords:
            if kw in combined:
                return True

        return False

    def _match_product_by_name(self, app_name: str) -> Optional[str]:
        """通过应用名匹配产品线"""
        if not app_name:
            return None
        name_lower = app_name.lower()
        for pl_name, pl_info in PRODUCT_LINES.items():
            for kw in pl_info['name_keywords']:
                if kw.lower() in name_lower:
                    return pl_name
        return None

    def _match_product_by_keyword(self, keyword: str) -> Optional[str]:
        """通过搜索关键词反推产品线"""
        kw_lower = keyword.lower()
        for pl_name, pl_info in PRODUCT_LINES.items():
            for name_kw in pl_info['name_keywords']:
                if name_kw.lower() in kw_lower:
                    return pl_name
        return None

    def _extract_enterprise_name(self, app_name: str,
                                  product_line: str) -> Optional[str]:
        """从应用名中提取企业名"""
        if not app_name:
            return None

        pl_info = PRODUCT_LINES.get(product_line, {})
        cleaned = app_name

        for kw in pl_info.get('name_keywords', []):
            cleaned = cleaned.replace(kw, '')

        # 清理后缀
        cleaned = re.sub(r'[版专属定制客户端]+$', '', cleaned).strip()
        cleaned = cleaned.strip('-_ ')

        if cleaned and len(cleaned) >= 2:
            return cleaned
        return None

    def _is_valid_package(self, name: str) -> bool:
        """验证包名有效性（排除域名）"""
        if not name or '.' not in name:
            return False
        parts = name.split('.')
        if len(parts) < 2:
            return False
        # 排除常见非包名
        excluded = [
            'www.', 'http.', 'https.', 'com.cn',
            'jquery.', 'bootstrap.', 'google.analytics',
        ]
        for exc in excluded:
            if name.startswith(exc):
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

    def close(self):
        pass
