"""
通用HTML解析工具
"""
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from utils.logger import get_logger

logger = get_logger('html_parser')


class HTMLParser:
    """通用HTML解析器"""

    def __init__(self, html: str, base_url: str = ''):
        self.soup = BeautifulSoup(html, 'lxml')
        self.base_url = base_url

    def get_text(self) -> str:
        """获取页面纯文本"""
        return self.soup.get_text(separator=' ', strip=True)

    def get_title(self) -> str:
        """获取页面标题"""
        title = self.soup.find('title')
        return title.get_text(strip=True) if title else ''

    def get_links(self, pattern: Optional[str] = None) -> list[dict]:
        """
        获取页面所有链接
        Args:
            pattern: 可选的URL正则过滤
        """
        links = []
        for a in self.soup.find_all('a', href=True):
            href = a['href']
            if self.base_url:
                href = urljoin(self.base_url, href)
            text = a.get_text(strip=True)

            if pattern and not re.search(pattern, href, re.IGNORECASE):
                continue

            links.append({
                'url': href,
                'text': text,
            })
        return links

    def find_download_links(self) -> list[dict]:
        """
        查找页面中的App下载链接
        识别APK下载链接或应用商店链接
        """
        download_keywords = [
            r'\.apk', r'android', r'安卓.*下载', r'app.*下载',
            r'下载.*app', r'移动客户端', r'手机版',
        ]
        combined_pattern = '|'.join(download_keywords)

        results = []
        for a in self.soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            # 检查链接URL或文字是否匹配下载关键词
            if (re.search(combined_pattern, href, re.IGNORECASE) or
                    re.search(combined_pattern, text, re.IGNORECASE)):
                if self.base_url:
                    href = urljoin(self.base_url, href)
                results.append({
                    'url': href,
                    'text': text,
                    'type': self._classify_download_link(href),
                })
        return results

    def _classify_download_link(self, url: str) -> str:
        """分类下载链接类型"""
        domain = urlparse(url).netloc.lower()

        # 应用商店域名
        store_domains = {
            'appgallery.huawei.com': 'huawei_store',
            'app.mi.com': 'xiaomi_store',
            'store.oppomobile.com': 'oppo_store',
            'h5.appstore.vivo.com.cn': 'vivo_store',
            'sj.qq.com': 'tencent_store',
            'www.wandoujia.com': 'wandoujia',
            'www.coolapk.com': 'coolapk',
            'apkpure.com': 'apkpure',
        }

        for store_domain, store_name in store_domains.items():
            if store_domain in domain:
                return store_name

        if url.lower().endswith('.apk'):
            return 'direct_apk'

        return 'other'

    def extract_app_info(self) -> dict:
        """
        从页面中提取应用信息（通用方法）
        尝试从meta标签、结构化数据中提取
        """
        info = {}

        # 从meta标签提取
        for meta in self.soup.find_all('meta'):
            name = meta.get('name', '').lower()
            prop = meta.get('property', '').lower()
            content = meta.get('content', '')

            if name in ('description', 'og:description') or prop == 'og:description':
                info['description'] = content[:500]
            elif name == 'keywords':
                info['keywords'] = content

        # 尝试提取JSON-LD结构化数据
        for script in self.soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if data.get('@type') == 'SoftwareApplication':
                        info['app_name'] = data.get('name', '')
                        info['version'] = data.get('version', '')
                        info['description'] = data.get('description', '')[:500]
                        if 'author' in data:
                            author = data['author']
                            if isinstance(author, dict):
                                info['developer'] = author.get('name', '')
            except (json.JSONDecodeError, TypeError):
                continue

        return info

    def find_text_by_keywords(self, keywords: list[str]) -> list[str]:
        """
        在页面文本中查找包含指定关键词的段落
        """
        results = []
        text_elements = self.soup.find_all(['p', 'div', 'span', 'li', 'td', 'h1', 'h2', 'h3', 'h4'])
        for elem in text_elements:
            text = elem.get_text(strip=True)
            if text and len(text) > 5:
                for kw in keywords:
                    if kw in text:
                        results.append(text[:200])
                        break
        return results


def extract_domain(url: str) -> str:
    """从URL提取域名"""
    parsed = urlparse(url)
    return parsed.netloc


def is_valid_url(url: str) -> bool:
    """检查URL是否合法"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def extract_package_name_from_url(url: str) -> Optional[str]:
    """
    尝试从URL中提取安卓包名
    例如: https://app.mi.com/details?id=com.tencent.wework
    """
    patterns = [
        r'[?&]id=([a-zA-Z][a-zA-Z0-9_.]*)',
        r'[?&]package=([a-zA-Z][a-zA-Z0-9_.]*)',
        r'/package/([a-zA-Z][a-zA-Z0-9_.]*)',
        r'/details/([a-zA-Z][a-zA-Z0-9_.]*)',
        r'/app/([a-zA-Z][a-zA-Z0-9_.]*)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            pkg = match.group(1)
            # 简单验证：至少包含一个点号
            if '.' in pkg:
                return pkg
    return None
