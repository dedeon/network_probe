"""
第三级爬虫 - 华为应用市场 (AppGallery)
通过搜索API和详情页获取应用信息
"""
import re
import json
from typing import Optional
from urllib.parse import quote_plus

from level3_appstore.base_store_spider import BaseStoreSpider
from utils.logger import get_logger

logger = get_logger('huawei_spider')


class HuaweiSpider(BaseStoreSpider):
    """
    华为应用市场爬虫
    使用华为AppGallery Web端接口进行搜索和详情获取
    """

    STORE_KEY = 'huawei'
    STORE_NAME = '华为应用市场'
    NEEDS_JS = True

    # 华为应用市场Web API
    SEARCH_API = 'https://web-drcn.hispace.dbankcloud.cn/uowap/index'
    DETAIL_API = 'https://web-drcn.hispace.dbankcloud.cn/uowap/index'

    def search(self, keyword: str) -> list[dict]:
        """搜索华为应用市场"""
        results = []

        params = {
            'method': 'internal.getTabDetail',
            'serviceType': 20,
            'reqPageNum': 1,
            'maxResults': 25,
            'uri': f'searchword|{keyword}',
            'keyword': keyword,
            'zone': '',
            'locale': 'zh',
        }

        data = self.fetch_json(self.SEARCH_API, params=params)
        if not data:
            return results

        try:
            layout_data = data.get('layoutData', [])
            for layout in layout_data:
                data_list = layout.get('dataList', [])
                for item in data_list:
                    app = self._parse_search_item(item)
                    if app:
                        results.append(app)
        except (KeyError, TypeError) as e:
            logger.error(f"华为搜索结果解析失败: {e}")

        logger.info(f"华为搜索 '{keyword}' 获得 {len(results)} 条结果")
        return results

    def parse_detail_page(self, url: str) -> Optional[dict]:
        """解析华为应用详情"""
        # 从URL提取appId
        app_id = self._extract_app_id(url)
        if not app_id:
            return None

        params = {
            'method': 'internal.getTabDetail',
            'serviceType': 20,
            'reqPageNum': 1,
            'maxResults': 25,
            'uri': f'app|{app_id}',
            'zone': '',
            'locale': 'zh',
        }

        data = self.fetch_json(self.DETAIL_API, params=params)
        if not data:
            return None

        try:
            layout_data = data.get('layoutData', [])
            for layout in layout_data:
                data_list = layout.get('dataList', [])
                for item in data_list:
                    return self._parse_detail_item(item)
        except (KeyError, TypeError) as e:
            logger.error(f"华为详情解析失败: {e}")

        return None

    def _parse_search_item(self, item: dict) -> Optional[dict]:
        """解析搜索结果项"""
        try:
            package_name = item.get('package', '') or item.get('packageName', '')
            app_name = item.get('name', '') or item.get('appName', '')

            if not package_name or not app_name:
                return None

            app_id = item.get('appid', '') or item.get('appId', '')
            detail_url = f'https://appgallery.huawei.com/app/{app_id}' if app_id else ''

            return {
                'package_name': package_name,
                'app_name': app_name,
                'developer': item.get('developer', ''),
                'version': item.get('versionName', '') or item.get('version', ''),
                'download_count': str(item.get('downCountDesc', '')),
                'description': str(item.get('intro', ''))[:500],
                'update_date': item.get('releaseDate', ''),
                'url': detail_url,
            }
        except Exception as e:
            logger.debug(f"解析华为搜索项失败: {e}")
            return None

    def _parse_detail_item(self, item: dict) -> Optional[dict]:
        """解析详情页数据"""
        try:
            return {
                'package_name': item.get('package', '') or item.get('packageName', ''),
                'app_name': item.get('name', '') or item.get('appName', ''),
                'developer': item.get('developer', ''),
                'version': item.get('versionName', '') or item.get('version', ''),
                'version_code': str(item.get('versionCode', '')),
                'download_count': str(item.get('downCountDesc', '')),
                'description': str(item.get('intro', ''))[:500],
                'update_date': item.get('releaseDate', ''),
                'url': f'https://appgallery.huawei.com/app/{item.get("appid", "")}',
            }
        except Exception as e:
            logger.debug(f"解析华为详情失败: {e}")
            return None

    def _extract_app_id(self, url: str) -> Optional[str]:
        """从URL中提取appId"""
        patterns = [
            r'/app/([A-Za-z0-9]+)',
            r'appid=([A-Za-z0-9]+)',
            r'id=([A-Za-z0-9]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
