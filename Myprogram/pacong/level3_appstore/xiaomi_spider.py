"""
第三级爬虫 - 小米应用商店
通过搜索页和详情页爬取应用信息
"""
import re
import json
from typing import Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from level3_appstore.base_store_spider import BaseStoreSpider
from utils.logger import get_logger

logger = get_logger('xiaomi_spider')


class XiaomiSpider(BaseStoreSpider):
    """
    小米应用商店爬虫
    小米应用商店(app.mi.com)为服务端渲染，可直接爬取HTML
    """

    STORE_KEY = 'xiaomi'
    STORE_NAME = '小米应用商店'
    NEEDS_JS = False

    SEARCH_URL = 'https://app.mi.com/searchAll'
    DETAIL_URL = 'https://app.mi.com/details'

    def search(self, keyword: str) -> list[dict]:
        """搜索小米应用商店"""
        results = []

        html = self.fetch_page(self.SEARCH_URL, params={'keywords': keyword})
        if not html:
            return results

        soup = BeautifulSoup(html, 'lxml')
        results.extend(self._parse_search_results(soup))

        logger.info(f"小米搜索 '{keyword}' 获得 {len(results)} 条结果")
        return results

    def parse_detail_page(self, url: str) -> Optional[dict]:
        """解析小米应用详情页"""
        html = self.fetch_page(url)
        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')
        return self._parse_detail(soup, url)

    def _parse_search_results(self, soup: BeautifulSoup) -> list[dict]:
        """解析搜索结果页"""
        results = []

        # 搜索结果列表
        app_items = soup.select('.applist-app, .app-list li, .nlist .app-info')
        if not app_items:
            # 备用选择器
            app_items = soup.select('a[href*="/details?id="]')

        for item in app_items:
            app = self._parse_search_item(item)
            if app:
                results.append(app)

        return results

    def _parse_search_item(self, item) -> Optional[dict]:
        """解析单个搜索结果项"""
        try:
            # 提取应用名
            name_elem = item.select_one('.app-name, h5, .name')
            app_name = name_elem.get_text(strip=True) if name_elem else ''

            # 提取链接和包名
            link = item if item.name == 'a' else item.select_one('a[href*="/details"]')
            href = link.get('href', '') if link else ''

            package_name = ''
            pkg_match = re.search(r'[?&]id=([a-zA-Z][a-zA-Z0-9_.]+)', href)
            if pkg_match:
                package_name = pkg_match.group(1)

            if not package_name and not app_name:
                return None

            detail_url = f'https://app.mi.com{href}' if href.startswith('/') else href

            # 提取其他信息
            desc_elem = item.select_one('.app-desc, .desc, p')
            description = desc_elem.get_text(strip=True) if desc_elem else ''

            return {
                'package_name': package_name,
                'app_name': app_name or package_name,
                'description': description[:500],
                'url': detail_url,
            }
        except Exception as e:
            logger.debug(f"解析小米搜索项失败: {e}")
            return None

    def _parse_detail(self, soup: BeautifulSoup, url: str) -> Optional[dict]:
        """解析详情页"""
        try:
            info = {'url': url}

            # 从URL提取包名
            pkg_match = re.search(r'[?&]id=([a-zA-Z][a-zA-Z0-9_.]+)', url)
            if pkg_match:
                info['package_name'] = pkg_match.group(1)

            # 应用名
            title = soup.select_one('.app-name, .intro-titles h3, h3.name')
            if title:
                info['app_name'] = title.get_text(strip=True)

            # 开发者
            dev = soup.select_one('.developer, .dev-name')
            if dev:
                info['developer'] = dev.get_text(strip=True)

            # 详细信息区域
            detail_items = soup.select('.details-body .float-left, .app-info-item')
            for di in detail_items:
                text = di.get_text(strip=True)
                if '版本' in text:
                    ver_match = re.search(r'[\d.]+', text)
                    if ver_match:
                        info['version'] = ver_match.group()
                elif '大小' in text or '体积' in text:
                    pass  # 可选存储
                elif '更新' in text or '日期' in text:
                    date_match = re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', text)
                    if date_match:
                        info['update_date'] = date_match.group()

            # 描述
            desc = soup.select_one('.pslide, .app-desc, .desc-info')
            if desc:
                info['description'] = desc.get_text(strip=True)[:500]

            # 下载量
            download = soup.select_one('.download-num, .app-intro span')
            if download:
                dl_text = download.get_text(strip=True)
                if '下载' in dl_text or '万' in dl_text or '亿' in dl_text:
                    info['download_count'] = dl_text

            return info if info.get('package_name') else None
        except Exception as e:
            logger.error(f"解析小米详情页失败: {e}")
            return None
