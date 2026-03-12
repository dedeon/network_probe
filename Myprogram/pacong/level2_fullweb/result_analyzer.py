"""
第二级爬虫 - 搜索结果分析与链接分类
对搜索引擎返回的结果进行分析、分类和有价值信息提取
"""
import re
from typing import Optional
from urllib.parse import urlparse, parse_qs

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PRODUCT_LINES, APP_STORES
from utils.logger import get_logger

logger = get_logger('result_analyzer')


class ResultAnalyzer:
    """
    搜索结果分析器
    - 对搜索结果URL进行分类（应用商店/企业官网/APK站/新闻等）
    - 从标题、摘要、URL中提取包名和应用名
    - 产品线匹配与定制包判定
    """

    # URL分类：应用商店域名 → 类型标记
    STORE_DOMAINS = {}
    for store_key, store_cfg in APP_STORES.items():
        STORE_DOMAINS[store_cfg['domain']] = store_key

    # 额外的已知商店域名
    EXTRA_STORE_DOMAINS = {
        'play.google.com': 'google_play',
        'apps.apple.com': 'apple_store',
        'm.app.so.com': '360_store',
        'shouji.baidu.com': 'baidu_store',
        'app.hicloud.com': 'huawei_store',
    }

    # APK收录站域名
    APK_SITE_DOMAINS = [
        'apkpure.com', 'apkmirror.com', 'apkcombo.com',
        'apk-dl.com', 'apksfull.com', 'apkmonk.com',
        'uptodown.com', 'malavida.com',
        'www.anzhi.com', 'www.pp.cn', 'www.liqucn.com',
        'www.appchina.com', 'www.mumayi.com',
    ]

    # 政务门户域名模式
    GOV_DOMAIN_PATTERN = re.compile(r'\.gov\.cn$', re.IGNORECASE)

    # 包名提取正则
    PACKAGE_NAME_PATTERNS = [
        re.compile(r'[?&]id=([a-zA-Z][a-zA-Z0-9_.]+)'),
        re.compile(r'[?&]package=([a-zA-Z][a-zA-Z0-9_.]+)'),
        re.compile(r'/package/([a-zA-Z][a-zA-Z0-9_.]+)'),
        re.compile(r'/details/([a-zA-Z][a-zA-Z0-9_.]+)'),
        re.compile(r'/apk/([a-zA-Z][a-zA-Z0-9_.]+)'),
        # 通用安卓包名模式（至少两段，如 com.xxx.yyy）
        re.compile(r'\b([a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9]*){2,})\b'),
    ]

    # 应用名提取：从标题中提取带有产品关键词的应用名
    APP_NAME_PATTERNS = []
    for pl_name, pl_info in PRODUCT_LINES.items():
        for kw in pl_info['name_keywords']:
            # "XX企业微信"、"XX版钉钉"等模式
            APP_NAME_PATTERNS.append(
                re.compile(
                    rf'([\u4e00-\u9fa5]{{2,15}}(?:版|专属|定制)?{re.escape(kw)})',
                    re.IGNORECASE,
                )
            )
            APP_NAME_PATTERNS.append(
                re.compile(
                    rf'({re.escape(kw)}[\u4e00-\u9fa5]{{0,10}}(?:版|专属|定制|客户端))',
                    re.IGNORECASE,
                )
            )

    # 结果类型枚举
    TYPE_APP_STORE = 'app_store'
    TYPE_APK_SITE = 'apk_site'
    TYPE_GOV_PORTAL = 'gov_portal'
    TYPE_ENTERPRISE_SITE = 'enterprise_site'
    TYPE_NEWS = 'news'
    TYPE_OTHER = 'other'

    def classify_url(self, url: str) -> dict:
        """
        分类URL并提取元信息
        Returns:
            {
                'type': 'app_store' | 'apk_site' | 'gov_portal' | 'enterprise_site' | 'news' | 'other',
                'store_key': str or None,      # 应用商店标识
                'domain': str,                 # 域名
                'package_name': str or None,   # 从URL提取的包名
            }
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
        except Exception:
            return {
                'type': self.TYPE_OTHER,
                'store_key': None,
                'domain': '',
                'package_name': None,
            }

        result = {
            'domain': domain,
            'store_key': None,
            'package_name': self._extract_package_from_url(url),
        }

        # 1. 应用商店
        for store_domain, store_key in self.STORE_DOMAINS.items():
            if store_domain in domain:
                result['type'] = self.TYPE_APP_STORE
                result['store_key'] = store_key
                return result

        for store_domain, store_key in self.EXTRA_STORE_DOMAINS.items():
            if store_domain in domain:
                result['type'] = self.TYPE_APP_STORE
                result['store_key'] = store_key
                return result

        # 2. APK收录站
        for apk_domain in self.APK_SITE_DOMAINS:
            if apk_domain in domain:
                result['type'] = self.TYPE_APK_SITE
                return result

        # 3. 政务门户
        if self.GOV_DOMAIN_PATTERN.search(domain):
            result['type'] = self.TYPE_GOV_PORTAL
            return result

        # 4. 新闻/媒体站
        news_domains = [
            '36kr.com', 'zhihu.com', 'sohu.com', '163.com',
            'sina.com.cn', 'qq.com', 'huxiu.com', 'tmtpost.com',
            'leiphone.com', 'csdn.net', 'jianshu.com',
        ]
        for news_domain in news_domains:
            if news_domain in domain:
                result['type'] = self.TYPE_NEWS
                return result

        # 5. 企业官网（含下载路径关键词）
        path_lower = parsed.path.lower()
        enterprise_path_keywords = [
            '/download', '/app', '/mobile', '/android',
            '/apk', '/client', '/软件下载',
        ]
        for kw in enterprise_path_keywords:
            if kw in path_lower:
                result['type'] = self.TYPE_ENTERPRISE_SITE
                return result

        # 默认归类为其他（可能是企业官网首页等）
        result['type'] = self.TYPE_OTHER
        return result

    def extract_app_info_from_text(self, title: str, snippet: str,
                                    url: str) -> dict:
        """
        从搜索结果的标题、摘要和URL中提取应用信息
        Returns:
            {
                'package_name': str or None,
                'app_name': str or None,
                'product_line': str or None,
                'enterprise_name': str or None,
            }
        """
        info = {
            'package_name': None,
            'app_name': None,
            'product_line': None,
            'enterprise_name': None,
        }

        combined_text = f"{title} {snippet}"

        # 1. 从URL中提取包名
        info['package_name'] = self._extract_package_from_url(url)

        # 2. 从文本中提取包名
        if not info['package_name']:
            info['package_name'] = self._extract_package_from_text(combined_text)

        # 3. 匹配产品线
        info['product_line'] = self._match_product_line(combined_text, info['package_name'])

        # 4. 提取应用名
        info['app_name'] = self._extract_app_name(combined_text)

        # 5. 提取企业名
        info['enterprise_name'] = self._extract_enterprise_name(
            combined_text, info.get('app_name', '')
        )

        return info

    def is_relevant_result(self, title: str, snippet: str, url: str) -> bool:
        """
        判断搜索结果是否与定制包相关
        """
        combined = f"{title} {snippet} {url}".lower()

        # 必须包含至少一个产品线关键词
        has_product = False
        for pl_info in PRODUCT_LINES.values():
            for kw in pl_info['name_keywords']:
                if kw.lower() in combined:
                    has_product = True
                    break
            if has_product:
                break

        if not has_product:
            # 检查包名模式
            for pl_info in PRODUCT_LINES.values():
                for pattern in pl_info['package_patterns']:
                    if pattern.search(combined):
                        has_product = True
                        break
                if has_product:
                    break

        if not has_product:
            return False

        # 必须包含与App/下载相关的关键词
        app_keywords = [
            'app', 'apk', '下载', 'download', '安卓', 'android',
            '客户端', '移动', '手机', '应用', '定制', '专属',
            '版本', 'version', '安装',
        ]
        for kw in app_keywords:
            if kw in combined:
                return True

        # URL本身指向应用商店或APK站
        url_info = self.classify_url(url)
        if url_info['type'] in (self.TYPE_APP_STORE, self.TYPE_APK_SITE):
            return True

        return False

    def match_product_line_for_package(self, package_name: str) -> Optional[str]:
        """根据包名匹配产品线"""
        if not package_name:
            return None
        for pl_name, pl_info in PRODUCT_LINES.items():
            for pattern in pl_info['package_patterns']:
                if pattern.search(package_name):
                    return pl_name
        return None

    def _extract_package_from_url(self, url: str) -> Optional[str]:
        """从URL中提取包名"""
        for pattern in self.PACKAGE_NAME_PATTERNS[:5]:  # 前5个是URL专用模式
            match = pattern.search(url)
            if match:
                pkg = match.group(1)
                if '.' in pkg and len(pkg) >= 5:
                    return pkg
        return None

    def _extract_package_from_text(self, text: str) -> Optional[str]:
        """从文本中提取包名"""
        # 使用通用包名正则
        pattern = self.PACKAGE_NAME_PATTERNS[-1]
        matches = pattern.findall(text)
        for pkg in matches:
            if self._is_valid_package_name(pkg):
                return pkg
        return None

    # 常见域名后缀，用于排除误匹配
    DOMAIN_SUFFIXES = {
        '.com', '.cn', '.org', '.net', '.gov', '.edu', '.io', '.cc',
        '.info', '.biz', '.me', '.co', '.tv', '.app', '.dev',
    }

    def _is_valid_package_name(self, name: str) -> bool:
        """验证是否为合法的Android包名（排除域名）"""
        if not name or '.' not in name:
            return False
        parts = name.split('.')
        if len(parts) < 2:
            return False
        # 排除常见非包名的域名
        excluded = ['www', 'http', 'https', 'com.cn', 'org.cn']
        if name in excluded:
            return False
        # 排除域名：检查是否以常见域名后缀结尾
        for suffix in self.DOMAIN_SUFFIXES:
            if name.endswith(suffix) or name.endswith(suffix.lstrip('.')):
                # 如果看起来像域名（如 xxx.qq.com），则排除
                # 但 com.xxx.yyy 这种安卓包名格式保留
                if not name.startswith('com.') and not name.startswith('org.') and not name.startswith('cn.'):
                    return False
        # 排除已知域名模式
        domain_patterns = [
            'qq.com', 'baidu.com', 'weixin.qq', 'sogou.com',
            'bing.com', 'google.com', 'github.com', 'gitee.com',
            'aliyun.com', 'taobao.com', 'jd.com', 'sina.com',
            'dldir1.qq', 'cdn.', 'static.',
        ]
        for dp in domain_patterns:
            if dp in name:
                return False
        # 必须以字母开头
        for part in parts:
            if not part or not part[0].isalpha():
                return False
        return True

    def _match_product_line(self, text: str,
                            package_name: Optional[str] = None) -> Optional[str]:
        """匹配产品线"""
        # 优先按包名匹配
        if package_name:
            pl = self.match_product_line_for_package(package_name)
            if pl:
                return pl

        # 按关键词匹配（取第一个命中的）
        text_lower = text.lower()
        for pl_name, pl_info in PRODUCT_LINES.items():
            for kw in pl_info['name_keywords']:
                if kw.lower() in text_lower:
                    return pl_name
        return None

    def _extract_app_name(self, text: str) -> Optional[str]:
        """从文本中提取应用名"""
        for pattern in self.APP_NAME_PATTERNS:
            match = pattern.search(text)
            if match:
                name = match.group(1).strip()
                if 3 <= len(name) <= 30:
                    return name
        return None

    def _extract_enterprise_name(self, text: str,
                                  app_name: str = '') -> Optional[str]:
        """从文本中提取企业名称"""
        # 方法1: 从应用名中提取（去掉产品关键词）
        if app_name:
            for pl_info in PRODUCT_LINES.values():
                for kw in pl_info['name_keywords']:
                    cleaned = app_name.replace(kw, '').strip()
                    if cleaned and len(cleaned) >= 2:
                        # 去掉 "版"、"专属"等后缀
                        cleaned = re.sub(r'[版专属定制客户端]+$', '', cleaned).strip()
                        if cleaned and len(cleaned) >= 2:
                            return cleaned

        # 方法2: 正则提取组织名
        org_pattern = re.compile(
            r'([\u4e00-\u9fa5]{2,15}'
            r'(?:集团|公司|银行|保险|证券|医院|大学|学院'
            r'|政府|管理局|委员会|中心|部门|省|市|区|县))'
        )
        matches = org_pattern.findall(text)
        if matches:
            # 返回最长的匹配（通常更完整）
            return max(matches, key=len)

        return None

    def analyze_search_results(self, results: list, enterprise_name: str = '',
                                product_line: str = '') -> list[dict]:
        """
        批量分析搜索结果，返回有价值的结果列表
        Args:
            results: SearchResult列表
            enterprise_name: 搜索的企业名
            product_line: 搜索的产品线
        Returns:
            [{'url', 'title', 'snippet', 'type', 'store_key', 'package_name',
              'app_name', 'product_line', 'enterprise_name', 'relevance_score'}]
        """
        analyzed = []

        for r in results:
            title = getattr(r, 'title', r.get('title', '')) if isinstance(r, dict) else r.title
            url = getattr(r, 'url', r.get('url', '')) if isinstance(r, dict) else r.url
            snippet = getattr(r, 'snippet', r.get('snippet', '')) if isinstance(r, dict) else r.snippet

            # URL分类
            url_info = self.classify_url(url)

            # 提取应用信息
            app_info = self.extract_app_info_from_text(title, snippet, url)

            # 补充上下文信息
            if not app_info['enterprise_name'] and enterprise_name:
                app_info['enterprise_name'] = enterprise_name
            if not app_info['product_line'] and product_line:
                app_info['product_line'] = product_line

            # 计算相关度评分
            relevance = self._calc_relevance(
                title, snippet, url, url_info, app_info, enterprise_name
            )

            analyzed.append({
                'url': url,
                'title': title,
                'snippet': snippet,
                'type': url_info['type'],
                'store_key': url_info['store_key'],
                'domain': url_info['domain'],
                'package_name': app_info['package_name'] or url_info.get('package_name'),
                'app_name': app_info['app_name'],
                'product_line': app_info['product_line'],
                'enterprise_name': app_info['enterprise_name'],
                'relevance_score': relevance,
            })

        # 按相关度排序
        analyzed.sort(key=lambda x: x['relevance_score'], reverse=True)
        return analyzed

    def _calc_relevance(self, title: str, snippet: str, url: str,
                        url_info: dict, app_info: dict,
                        enterprise_name: str = '') -> float:
        """
        计算搜索结果的相关度评分（0~1）
        """
        score = 0.0
        combined = f"{title} {snippet}".lower()

        # 1. URL类型加分
        type_scores = {
            self.TYPE_APP_STORE: 0.3,
            self.TYPE_APK_SITE: 0.25,
            self.TYPE_ENTERPRISE_SITE: 0.2,
            self.TYPE_GOV_PORTAL: 0.15,
            self.TYPE_NEWS: 0.05,
            self.TYPE_OTHER: 0.0,
        }
        score += type_scores.get(url_info['type'], 0)

        # 2. 包名命中加分
        if app_info.get('package_name'):
            score += 0.25

        # 3. 应用名命中加分
        if app_info.get('app_name'):
            score += 0.15

        # 4. 产品线命中加分
        if app_info.get('product_line'):
            score += 0.1

        # 5. 企业名命中加分
        if enterprise_name and enterprise_name.lower() in combined:
            score += 0.1

        # 6. 下载/App相关关键词加分
        download_keywords = ['下载', 'download', 'apk', '安装', '客户端', 'app']
        for kw in download_keywords:
            if kw in combined:
                score += 0.02
                break

        return min(score, 1.0)
