"""
第三级爬虫 - 豌豆荚
搜索返回数字ID，通过详情页提取完整包名和信息
"""
import re
import json
from typing import Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from level3_appstore.base_store_spider import BaseStoreSpider
from utils.logger import get_logger

logger = get_logger('wandoujia_spider')


class WandoujiaSpider(BaseStoreSpider):
    """
    豌豆荚爬虫
    策略：搜索页获取应用数字ID列表 → 逐个访问详情页提取包名和元数据
    """

    STORE_KEY = 'wandoujia'
    STORE_NAME = '豌豆荚'
    NEEDS_JS = False

    SEARCH_URL = 'https://www.wandoujia.com/search'
    DETAIL_BASE = 'https://www.wandoujia.com/apps'

    def search(self, keyword: str) -> list[dict]:
        """搜索豌豆荚"""
        results = []

        html = self.fetch_page(self.SEARCH_URL, params={'key': keyword})
        if not html:
            return results

        soup = BeautifulSoup(html, 'lxml')

        # 搜索结果中找到应用ID列表
        app_ids = set()
        for a in soup.select('a[href*="/apps/"]'):
            href = a.get('href', '')
            m = re.search(r'/apps/(\d+)', href)
            if m:
                app_ids.add(m.group(1))
            else:
                # 也可能直接用包名作为路径
                m2 = re.search(r'/apps/([a-zA-Z][a-zA-Z0-9_.]+)', href)
                if m2:
                    pkg = m2.group(1)
                    if '.' in pkg:
                        results.append({
                            'package_name': pkg,
                            'app_name': a.get_text(strip=True) or pkg,
                            'url': href if href.startswith('http') else f'https://www.wandoujia.com{href}',
                        })

        # 对每个数字ID，访问详情页获取包名
        for app_id in list(app_ids)[:10]:  # 限制每次搜索最多10个详情页
            detail = self._fetch_detail_by_id(app_id)
            if detail:
                results.append(detail)

        logger.info(f"豌豆荚搜索 '{keyword}' 获得 {len(results)} 条结果")
        return results

    def parse_detail_page(self, url: str) -> Optional[dict]:
        """解析豌豆荚应用详情页"""
        html = self.fetch_page(url)
        if not html:
            return None
        return self._parse_detail_html(html, url)

    def _fetch_detail_by_id(self, app_id: str) -> Optional[dict]:
        """通过数字ID获取详情"""
        url = f'{self.DETAIL_BASE}/{app_id}'
        html = self.fetch_page(url)
        if not html:
            return None
        return self._parse_detail_html(html, url)

    def _parse_detail_html(self, html: str, url: str) -> Optional[dict]:
        """从详情页HTML中提取应用信息"""
        try:
            soup = BeautifulSoup(html, 'lxml')
            info = {'url': url}

            # 1. 从页面文本中提取包名（com.xxx.yyy格式）
            text = soup.get_text()
            pkg_matches = re.findall(r'\bcom\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9]*)+\b', text)
            if pkg_matches:
                # 取第一个看起来像安卓包名的
                for pkg in pkg_matches:
                    if not self._is_domain(pkg):
                        info['package_name'] = pkg
                        break

            # 也检查URL中的包名
            if not info.get('package_name'):
                m = re.search(r'/apps/([a-zA-Z][a-zA-Z0-9_.]+)', url)
                if m and '.' in m.group(1):
                    info['package_name'] = m.group(1)

            # 2. 应用名
            name_el = soup.select_one('.app-name')
            if name_el:
                # .app-name 可能包含span
                span = name_el.select_one('span')
                info['app_name'] = (span or name_el).get_text(strip=True)

            # 3. 开发者 - 从页面底部信息或详情区域提取
            for sel in ['.dev-sites a', '.dev-name', 'a[href*="developer"]']:
                el = soup.select_one(sel)
                if el:
                    dev_text = el.get_text(strip=True)
                    if dev_text and len(dev_text) >= 2 and '豌豆' not in dev_text:
                        info['developer'] = dev_text
                        break

            # 4. 从详情信息列表提取版本、大小、日期
            detail_items = soup.select('.infos-list li, .info-list li')
            for di in detail_items:
                text_content = di.get_text(strip=True)
                # 版本号
                if re.match(r'^[\d.]+$', text_content) and '.' in text_content:
                    info['version'] = text_content
                # 日期
                elif re.match(r'^\d{4}/\d{2}/\d{2}', text_content):
                    info['update_date'] = text_content.split()[0].replace('/', '-')

            # 5. 下载量
            dl_el = soup.select_one('.install-count, .download-num')
            if dl_el:
                info['download_count'] = dl_el.get_text(strip=True)
            else:
                # 从detail-top区域提取
                dt = soup.select_one('.detail-top')
                if dt:
                    dl_m = re.search(r'([\d.]+万(?:次下载|人安装))', dt.get_text())
                    if dl_m:
                        info['download_count'] = dl_m.group(1)

            # 6. 描述
            desc_el = soup.select_one('.desc-info .content, .con, meta[name="description"]')
            if desc_el:
                if desc_el.name == 'meta':
                    info['description'] = desc_el.get('content', '')[:500]
                else:
                    info['description'] = desc_el.get_text(strip=True)[:500]

            if not info.get('package_name'):
                return None

            return info

        except Exception as e:
            logger.error(f"解析豌豆荚详情页失败: {e}")
            return None

    def _is_domain(self, name: str) -> bool:
        """检查是否是域名而非包名"""
        domain_patterns = [
            'wandoujia.com', 'qq.com', 'baidu.com', 'google.com',
            'android.com', 'googleapis.com', 'gstatic.com',
        ]
        for dp in domain_patterns:
            if dp in name:
                return True
        return False
