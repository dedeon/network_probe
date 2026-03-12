"""
第三级爬虫 - 应用宝 (腾讯应用市场)
搜索API已失效，通过直接访问详情页 /appdetail/{包名} 获取应用信息
"""
import re
import json
from typing import Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from level3_appstore.base_store_spider import BaseStoreSpider
from utils.logger import get_logger

logger = get_logger('tencent_spider')


class TencentSpider(BaseStoreSpider):
    """
    应用宝爬虫
    搜索功能不可用，通过以下方式获取数据：
    1. 用已知包名直接访问详情页
    2. 从页面 meta 标签和 __NEXT_DATA__ 提取应用信息
    """

    STORE_KEY = 'tencent'
    STORE_NAME = '应用宝'
    NEEDS_JS = False  # 可以从SSR的HTML和__NEXT_DATA__中提取

    DETAIL_URL = 'https://sj.qq.com/appdetail/{package_name}'

    def search(self, keyword: str) -> list[dict]:
        """
        应用宝搜索API已不可用。
        如果keyword看起来像包名(含.)，直接查详情页。
        否则返回空结果。
        """
        results = []

        # 如果关键词本身是包名格式，直接查详情
        if '.' in keyword and re.match(r'^[a-zA-Z][a-zA-Z0-9_.]+$', keyword):
            detail = self.get_detail_by_package(keyword)
            if detail:
                results.append(detail)
            return results

        # 搜索API不可用，返回空
        logger.debug(f"应用宝搜索不可用，跳过关键词: {keyword}")
        return results

    def get_detail_by_package(self, package_name: str) -> Optional[dict]:
        """通过包名直接获取应用详情"""
        url = self.DETAIL_URL.format(package_name=package_name)
        html = self.fetch_page(url)
        if not html:
            return None
        return self._parse_detail_html(html, url, package_name)

    def parse_detail_page(self, url: str) -> Optional[dict]:
        """解析应用宝应用详情"""
        # 从URL提取包名
        m = re.search(r'/appdetail/([a-zA-Z][a-zA-Z0-9_.]+)', url)
        if not m:
            m = re.search(r'[?&]apk(?:Name)?=([a-zA-Z][a-zA-Z0-9_.]+)', url)
        if not m:
            return None

        package_name = m.group(1)
        html = self.fetch_page(url)
        if not html:
            return None
        return self._parse_detail_html(html, url, package_name)

    def _parse_detail_html(self, html: str, url: str,
                           package_name: str) -> Optional[dict]:
        """从详情页HTML提取应用信息"""
        try:
            soup = BeautifulSoup(html, 'lxml')
            info = {
                'package_name': package_name,
                'url': url,
            }

            # 1. 从title提取应用名
            title_el = soup.select_one('title')
            if title_el:
                title_text = title_el.get_text(strip=True)
                # 格式: "企业微信app官网下载-企业微信下载安装-应用宝"
                app_name = title_text.split('app')[0].strip()
                if not app_name:
                    app_name = title_text.split('下载')[0].strip()
                if app_name and app_name != '应用宝':
                    info['app_name'] = app_name

            # 2. 从H1标签
            if not info.get('app_name'):
                h1 = soup.select_one('h1')
                if h1:
                    info['app_name'] = h1.get_text(strip=True)

            # 3. 从meta标签提取描述
            for meta in soup.find_all('meta'):
                name = meta.get('name', '') or meta.get('property', '')
                content = meta.get('content', '')
                if 'description' in name.lower() and content:
                    info['description'] = content[:500]
                    break

            # 4. 尝试从__NEXT_DATA__提取更多信息
            nd_match = re.search(
                r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                html, re.DOTALL
            )
            if nd_match:
                try:
                    nd = json.loads(nd_match.group(1))
                    self._extract_from_next_data(nd, info)
                except json.JSONDecodeError:
                    pass

            if not info.get('app_name'):
                return None

            return info

        except Exception as e:
            logger.error(f"应用宝详情解析失败: {e}")
            return None

    def _extract_from_next_data(self, nd: dict, info: dict):
        """从__NEXT_DATA__ JSON中提取应用信息"""
        try:
            pp = nd.get('props', {}).get('pageProps', {})

            # seoMeta 中可能有额外信息
            seo = pp.get('seoMeta', {})
            if seo:
                if not info.get('app_name') and seo.get('title'):
                    title = seo['title']
                    app_name = title.split('app')[0].strip()
                    if not app_name:
                        app_name = title.split('下载')[0].strip()
                    if app_name:
                        info['app_name'] = app_name

                if not info.get('description') and seo.get('description'):
                    info['description'] = seo['description'][:500]

            # 从 dynamicCardResponse 中提取
            dcr = pp.get('dynamicCardResponse', {})
            data = dcr.get('data', {})
            if isinstance(data, dict):
                components = data.get('components', [])
                for comp in components:
                    comp_data = comp.get('data', {})
                    if isinstance(comp_data, dict):
                        # 可能包含应用详情
                        app_name = comp_data.get('appName', '')
                        if app_name and not info.get('app_name'):
                            info['app_name'] = app_name
                        pkg = comp_data.get('pkgName', '')
                        if pkg and not info.get('package_name'):
                            info['package_name'] = pkg
                        dev = comp_data.get('authorName', '')
                        if dev and not info.get('developer'):
                            info['developer'] = dev
                        ver = comp_data.get('versionName', '')
                        if ver and not info.get('version'):
                            info['version'] = ver
                        dl = comp_data.get('appDownCount', '')
                        if dl and not info.get('download_count'):
                            info['download_count'] = str(dl)

        except Exception as e:
            logger.debug(f"解析__NEXT_DATA__失败: {e}")
