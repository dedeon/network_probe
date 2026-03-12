"""
第三级爬虫 - OPPO软件商店
通过搜索API获取应用信息
"""
import re
import json
from typing import Optional
from urllib.parse import quote_plus

from level3_appstore.base_store_spider import BaseStoreSpider
from utils.logger import get_logger

logger = get_logger('oppo_spider')


class OppoSpider(BaseStoreSpider):
    """
    OPPO软件商店爬虫
    使用OPPO软件商店的搜索API获取应用数据
    """

    STORE_KEY = 'oppo'
    STORE_NAME = 'OPPO软件商店'
    NEEDS_JS = True

    # OPPO软件商店搜索API
    SEARCH_API = 'https://store.oppomobile.com/api/market/search'
    DETAIL_API = 'https://store.oppomobile.com/api/market/detail'

    def search(self, keyword: str) -> list[dict]:
        """搜索OPPO软件商店"""
        results = []

        params = {
            'q': keyword,
            'pageNo': 1,
            'pageSize': 20,
        }

        # 尝试API方式
        data = self.fetch_json(self.SEARCH_API, params=params)
        if data and isinstance(data, dict):
            app_list = data.get('data', {}).get('list', [])
            if not app_list:
                app_list = data.get('data', {}).get('appList', [])
            for item in app_list:
                app = self._parse_api_item(item)
                if app:
                    results.append(app)
        else:
            # 备用：HTML页面爬取
            results.extend(self._search_html(keyword))

        logger.info(f"OPPO搜索 '{keyword}' 获得 {len(results)} 条结果")
        return results

    def parse_detail_page(self, url: str) -> Optional[dict]:
        """解析OPPO应用详情"""
        pkg_match = re.search(r'[?&]pkg(?:name)?=([a-zA-Z][a-zA-Z0-9_.]+)', url)
        if not pkg_match:
            return None

        package_name = pkg_match.group(1)
        params = {'pkgName': package_name}

        data = self.fetch_json(self.DETAIL_API, params=params)
        if not data or not isinstance(data, dict):
            return None

        try:
            detail = data.get('data', {})
            return {
                'package_name': detail.get('packageName', package_name),
                'app_name': detail.get('appName', ''),
                'developer': detail.get('developer', ''),
                'version': detail.get('versionName', ''),
                'version_code': str(detail.get('versionCode', '')),
                'download_count': str(detail.get('downloadCount', '')),
                'description': str(detail.get('description', ''))[:500],
                'update_date': detail.get('updateTime', ''),
                'url': url,
            }
        except Exception as e:
            logger.error(f"OPPO详情解析失败: {e}")
            return None

    def _search_html(self, keyword: str) -> list[dict]:
        """通过HTML页面搜索（备用方案）"""
        results = []
        url = f'https://store.oppomobile.com/search?q={quote_plus(keyword)}'
        html = self.fetch_page(url)
        if not html:
            return results

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')

        app_items = soup.select('.app-item, .search-item, a[href*="detail"]')
        for item in app_items:
            try:
                link = item if item.name == 'a' else item.select_one('a')
                href = link.get('href', '') if link else ''

                pkg_match = re.search(r'[?&]pkg(?:name)?=([a-zA-Z][a-zA-Z0-9_.]+)', href)
                package_name = pkg_match.group(1) if pkg_match else ''

                name_elem = item.select_one('.app-name, .name, h4')
                app_name = name_elem.get_text(strip=True) if name_elem else ''

                if package_name or app_name:
                    results.append({
                        'package_name': package_name,
                        'app_name': app_name or package_name,
                        'url': href if href.startswith('http') else f'https://store.oppomobile.com{href}',
                    })
            except Exception:
                continue

        return results

    def _parse_api_item(self, item: dict) -> Optional[dict]:
        """解析API返回的应用项"""
        try:
            package_name = item.get('packageName', '') or item.get('pkgName', '')
            app_name = item.get('appName', '') or item.get('name', '')

            if not package_name and not app_name:
                return None

            return {
                'package_name': package_name,
                'app_name': app_name,
                'developer': item.get('developer', ''),
                'version': item.get('versionName', ''),
                'download_count': str(item.get('downloadCount', '')),
                'description': str(item.get('description', ''))[:500],
                'url': f'https://store.oppomobile.com/detail?pkgname={package_name}' if package_name else '',
            }
        except Exception as e:
            logger.debug(f"OPPO API项解析失败: {e}")
            return None
