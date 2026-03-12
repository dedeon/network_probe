"""
第三级爬虫 - vivo应用商店
通过搜索API获取应用信息
"""
import re
import json
from typing import Optional
from urllib.parse import quote_plus

from level3_appstore.base_store_spider import BaseStoreSpider
from utils.logger import get_logger

logger = get_logger('vivo_spider')


class VivoSpider(BaseStoreSpider):
    """
    vivo应用商店爬虫
    使用vivo应用商店的Web端搜索API获取数据
    """

    STORE_KEY = 'vivo'
    STORE_NAME = 'vivo应用商店'
    NEEDS_JS = True

    # vivo应用商店搜索API
    SEARCH_API = 'https://h5-appstore-api.vivo.com.cn/search'
    DETAIL_API = 'https://h5-appstore-api.vivo.com.cn/detail'

    def search(self, keyword: str) -> list[dict]:
        """搜索vivo应用商店"""
        results = []

        params = {
            'keyword': keyword,
            'pageIndex': 1,
            'pageSize': 20,
        }

        data = self.fetch_json(self.SEARCH_API, params=params)
        if data and isinstance(data, dict):
            app_list = (data.get('data', {}).get('appList', [])
                        or data.get('data', {}).get('list', [])
                        or data.get('value', {}).get('listInfo', {}).get('list', []))
            for item in app_list:
                app = self._parse_item(item)
                if app:
                    results.append(app)
        else:
            # 备用方案
            results.extend(self._search_fallback(keyword))

        logger.info(f"vivo搜索 '{keyword}' 获得 {len(results)} 条结果")
        return results

    def parse_detail_page(self, url: str) -> Optional[dict]:
        """解析vivo应用详情"""
        # 从URL提取包名或ID
        pkg_match = re.search(r'[?&](?:id|pkg)=([a-zA-Z][a-zA-Z0-9_.]+)', url)
        if not pkg_match:
            return None

        identifier = pkg_match.group(1)
        params = {'id': identifier}

        data = self.fetch_json(self.DETAIL_API, params=params)
        if not data or not isinstance(data, dict):
            return None

        try:
            detail = data.get('data', {}) or data.get('value', {})
            return {
                'package_name': detail.get('packageName', '') or detail.get('pkgName', identifier),
                'app_name': detail.get('appName', '') or detail.get('name', ''),
                'developer': detail.get('developer', '') or detail.get('devName', ''),
                'version': detail.get('versionName', '') or detail.get('version', ''),
                'version_code': str(detail.get('versionCode', '')),
                'download_count': str(detail.get('downloadCount', '') or detail.get('downNum', '')),
                'description': str(detail.get('description', '') or detail.get('intro', ''))[:500],
                'update_date': detail.get('updateTime', '') or detail.get('lastUpdateTime', ''),
                'url': url,
            }
        except Exception as e:
            logger.error(f"vivo详情解析失败: {e}")
            return None

    def _search_fallback(self, keyword: str) -> list[dict]:
        """备用搜索方案：直接请求H5页面"""
        results = []
        url = f'https://h5.appstore.vivo.com.cn/search?keyword={quote_plus(keyword)}'
        html = self.fetch_page(url)
        if not html:
            return results

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')

        # 尝试从页面内嵌的JSON数据中提取
        for script in soup.find_all('script'):
            text = script.string or ''
            if 'packageName' in text or 'appName' in text:
                try:
                    # 提取JSON对象
                    json_match = re.search(r'\{.*"packageName".*\}', text, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group())
                        app = self._parse_item(data)
                        if app:
                            results.append(app)
                except (json.JSONDecodeError, Exception):
                    continue

        return results

    def _parse_item(self, item: dict) -> Optional[dict]:
        """解析应用项"""
        try:
            package_name = (item.get('packageName', '')
                           or item.get('pkgName', '')
                           or item.get('package', ''))
            app_name = (item.get('appName', '')
                       or item.get('name', '')
                       or item.get('title', ''))

            if not package_name and not app_name:
                return None

            return {
                'package_name': package_name,
                'app_name': app_name,
                'developer': item.get('developer', '') or item.get('devName', ''),
                'version': item.get('versionName', '') or item.get('version', ''),
                'download_count': str(item.get('downloadCount', '') or item.get('downNum', '')),
                'description': str(item.get('description', '') or item.get('intro', ''))[:500],
                'update_date': item.get('updateTime', ''),
                'url': f'https://h5.appstore.vivo.com.cn/#/detail?id={package_name}' if package_name else '',
            }
        except Exception as e:
            logger.debug(f"vivo项解析失败: {e}")
            return None
