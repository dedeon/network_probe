"""
第一级爬虫 - 产品官网案例页爬虫
从企业微信、钉钉、飞书的官网客户案例页/行业方案页中提取客户企业名称
"""
import re
import time
import random
from typing import Optional

import httpx
from bs4 import BeautifulSoup

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PRODUCT_LINES
from storage.db import CustomerDB
from level1_customers.customer_store import CustomerStore
from utils.ua_pool import ua_pool
from utils.rate_limiter import rate_limiter
from utils.logger import get_logger

logger = get_logger('official_site_spider')


class OfficialSiteSpider:
    """
    产品官网案例页爬虫
    从各产品官网的客户案例、行业方案、合作伙伴页面中提取客户企业名称
    """

    # 各产品官网的案例/客户页面URL列表
    TARGET_PAGES = {
        '企业微信': [
            {
                'url': 'https://work.weixin.qq.com/nl/customer-case',
                'desc': '企业微信客户案例页',
                'parse_method': 'parse_wecom_cases',
            },
            {
                'url': 'https://work.weixin.qq.com/nl/industry-solutions',
                'desc': '企业微信行业方案页',
                'parse_method': 'parse_wecom_industry',
            },
            {
                'url': 'https://work.weixin.qq.com/',
                'desc': '企业微信首页',
                'parse_method': 'parse_generic_page',
            },
        ],
        '钉钉': [
            {
                'url': 'https://page.dingtalk.com/wow/z/dingtalk/customer-case/customer-case',
                'desc': '钉钉客户案例页',
                'parse_method': 'parse_dingtalk_cases',
            },
            {
                'url': 'https://www.dingtalk.com/solution',
                'desc': '钉钉行业解决方案',
                'parse_method': 'parse_generic_page',
            },
            {
                'url': 'https://www.dingtalk.com/',
                'desc': '钉钉首页',
                'parse_method': 'parse_generic_page',
            },
        ],
        '飞书': [
            {
                'url': 'https://www.feishu.cn/customers',
                'desc': '飞书客户故事页',
                'parse_method': 'parse_feishu_customers',
            },
            {
                'url': 'https://www.feishu.cn/solutions',
                'desc': '飞书行业方案页',
                'parse_method': 'parse_generic_page',
            },
            {
                'url': 'https://www.feishu.cn/',
                'desc': '飞书首页',
                'parse_method': 'parse_generic_page',
            },
        ],
    }

    # 常见企业名称匹配正则（通用）
    ENTERPRISE_NAME_PATTERNS = [
        # 中文企业名：XX集团、XX公司、XX银行、XX大学、XX政府等
        re.compile(
            r'([\u4e00-\u9fa5]{2,15}?'
            r'(?:集团|公司|股份|控股|银行|保险|证券|基金|医院|大学|学院'
            r'|研究院|研究所|协会|委员会|管理局|政务|政府|省|市|区|县'
            r'|厅|局|办|部|院|委|中心|科技|网络|信息|互联网|金融'
            r'|地产|置业|建设|工程|制造|电子|汽车|能源|航空|铁路))'
        ),
    ]

    def __init__(self, customer_db: Optional[CustomerDB] = None):
        self.store = CustomerStore(customer_db)
        from utils.http_client import http_client
        self.http = http_client
        self.total_found = 0

    def run(self):
        """执行官网案例页爬取"""
        logger.info("开始爬取产品官网案例页...")

        for product_line, pages in self.TARGET_PAGES.items():
            logger.info(f"--- 处理产品线: {product_line} ---")

            for page_info in pages:
                url = page_info['url']
                desc = page_info['desc']
                parse_method = page_info['parse_method']

                logger.info(f"爬取: {desc} ({url})")

                try:
                    html = self._fetch_page(url)
                    if not html:
                        logger.warning(f"获取页面失败: {url}")
                        continue

                    # 调用对应的解析方法
                    parser = getattr(self, parse_method, self.parse_generic_page)
                    customers = parser(html, product_line, url)

                    if customers:
                        inserted = self.store.batch_add_customers(customers)
                        self.total_found += len(customers)
                        logger.info(f"  从 {desc} 提取到 {len(customers)} 个客户名，新入库 {inserted} 个")
                    else:
                        logger.info(f"  从 {desc} 未提取到客户名")

                except Exception as e:
                    logger.error(f"爬取 {desc} 失败: {e}")

                # 请求间隔
                time.sleep(random.uniform(3, 6))

        logger.info(f"官网案例页爬取完成，共发现 {self.total_found} 个客户名")
        self.store.print_stats()

    def _fetch_page(self, url: str) -> Optional[str]:
        """获取网页HTML（通过统一客户端，自动重试和反爬处理）"""
        return self.http.get_text(url)

    def parse_wecom_cases(self, html: str, product_line: str, url: str) -> list[dict]:
        """解析企业微信客户案例页"""
        soup = BeautifulSoup(html, 'lxml')
        customers = []

        # 方式1: 查找案例卡片中的企业名称
        for card in soup.select('.case-card, .customer-card, .case-item, '
                                '.customer-item, [class*="case"], [class*="customer"]'):
            name_elem = card.select_one(
                '.case-title, .customer-name, .name, h3, h4, '
                '.title, [class*="name"], [class*="title"]'
            )
            if name_elem:
                name = name_elem.get_text(strip=True)
                if name and len(name) >= 2:
                    customers.append({
                        'enterprise_name': name,
                        'product_line': product_line,
                        'source': f'work.weixin.qq.com/案例页',
                        'industry': self._extract_industry(card),
                    })

        # 方式2: 从Logo图片的alt属性提取
        for img in soup.select('img[alt]'):
            alt = img.get('alt', '').strip()
            if alt and len(alt) >= 2 and self._looks_like_enterprise(alt):
                customers.append({
                    'enterprise_name': alt,
                    'product_line': product_line,
                    'source': f'work.weixin.qq.com/Logo',
                })

        # 方式3: 通用正则提取
        customers.extend(self._extract_by_regex(html, product_line, url))

        return customers

    def parse_wecom_industry(self, html: str, product_line: str, url: str) -> list[dict]:
        """解析企业微信行业方案页"""
        return self._parse_solution_page(html, product_line, url, 'work.weixin.qq.com')

    def parse_dingtalk_cases(self, html: str, product_line: str, url: str) -> list[dict]:
        """解析钉钉客户案例页"""
        soup = BeautifulSoup(html, 'lxml')
        customers = []

        # 查找案例卡片
        for card in soup.select('.case-item, .customer-card, [class*="case"], '
                                '[class*="customer"], .card, .item'):
            name_elem = card.select_one(
                '.case-title, .name, .title, h3, h4, '
                '[class*="name"], [class*="title"]'
            )
            if name_elem:
                name = name_elem.get_text(strip=True)
                if name and len(name) >= 2:
                    customers.append({
                        'enterprise_name': name,
                        'product_line': product_line,
                        'source': 'dingtalk.com/案例页',
                        'industry': self._extract_industry(card),
                    })

        # Logo alt提取
        for img in soup.select('img[alt]'):
            alt = img.get('alt', '').strip()
            if alt and len(alt) >= 2 and self._looks_like_enterprise(alt):
                customers.append({
                    'enterprise_name': alt,
                    'product_line': product_line,
                    'source': 'dingtalk.com/Logo',
                })

        customers.extend(self._extract_by_regex(html, product_line, url))
        return customers

    def parse_feishu_customers(self, html: str, product_line: str, url: str) -> list[dict]:
        """解析飞书客户故事页"""
        soup = BeautifulSoup(html, 'lxml')
        customers = []

        # 查找客户卡片
        for card in soup.select('.customer-card, .story-card, [class*="customer"], '
                                '[class*="story"], .card, .item'):
            name_elem = card.select_one(
                '.customer-name, .company-name, .name, .title, h3, h4, '
                '[class*="name"], [class*="company"]'
            )
            if name_elem:
                name = name_elem.get_text(strip=True)
                if name and len(name) >= 2:
                    customers.append({
                        'enterprise_name': name,
                        'product_line': product_line,
                        'source': 'feishu.cn/客户故事',
                        'industry': self._extract_industry(card),
                    })

        # Logo alt
        for img in soup.select('img[alt]'):
            alt = img.get('alt', '').strip()
            if alt and len(alt) >= 2 and self._looks_like_enterprise(alt):
                customers.append({
                    'enterprise_name': alt,
                    'product_line': product_line,
                    'source': 'feishu.cn/Logo',
                })

        customers.extend(self._extract_by_regex(html, product_line, url))
        return customers

    def parse_generic_page(self, html: str, product_line: str, url: str) -> list[dict]:
        """通用页面解析 - 从文本中用正则/关键词提取企业名称"""
        return self._extract_by_regex(html, product_line, url)

    def _parse_solution_page(self, html: str, product_line: str,
                             url: str, domain: str) -> list[dict]:
        """解析行业方案页（通用）"""
        soup = BeautifulSoup(html, 'lxml')
        customers = []

        # 查找提及的客户名称
        for elem in soup.select('.case-name, .customer-name, .partner-name, '
                                '[class*="client"], [class*="partner"]'):
            name = elem.get_text(strip=True)
            if name and len(name) >= 2:
                customers.append({
                    'enterprise_name': name,
                    'product_line': product_line,
                    'source': f'{domain}/行业方案',
                })

        customers.extend(self._extract_by_regex(html, product_line, url))
        return customers

    def _extract_by_regex(self, html: str, product_line: str, url: str) -> list[dict]:
        """用正则从页面文本中提取企业名称"""
        soup = BeautifulSoup(html, 'lxml')

        # 移除脚本和样式
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()

        text = soup.get_text(separator=' ', strip=True)
        customers = []
        seen = set()

        for pattern in self.ENTERPRISE_NAME_PATTERNS:
            for match in pattern.finditer(text):
                name = match.group(1).strip()
                if name and name not in seen and self._looks_like_enterprise(name):
                    seen.add(name)
                    domain = url.split('/')[2] if '/' in url else url
                    customers.append({
                        'enterprise_name': name,
                        'product_line': product_line,
                        'source': f'{domain}/正则提取',
                    })

        return customers

    def _extract_industry(self, card_elem) -> str:
        """从卡片元素中提取行业标签"""
        industry_keywords = {
            '金融': ['金融', '银行', '保险', '证券', '基金'],
            '制造': ['制造', '工业', '汽车', '电子', '机械'],
            '零售': ['零售', '电商', '消费', '品牌'],
            '教育': ['教育', '大学', '学院', '学校'],
            '医疗': ['医疗', '医院', '健康', '医药'],
            '政务': ['政务', '政府', '公安', '法院'],
            '互联网': ['互联网', '科技', '软件', 'IT'],
            '地产': ['地产', '房产', '建筑', '置业'],
            '能源': ['能源', '电力', '石油', '矿业'],
        }

        card_text = card_elem.get_text(strip=True)
        for industry, keywords in industry_keywords.items():
            for kw in keywords:
                if kw in card_text:
                    return industry
        return ''

    def _looks_like_enterprise(self, name: str) -> bool:
        """判断一个名称是否像企业/组织名称"""
        if not name or len(name) < 3 or len(name) > 30:
            return False

        # 排除明显不是企业名的文本
        noise_starts = [
            '如何', '怎么', '为什么', '什么', '可以', '支持', '帮助',
            '揭秘', '谁给', '满足', '适配', '让', '将', '通过',
            '发表', '提供', '可用', '入转', '总结', '文档',
        ]
        for ns in noise_starts:
            if name.startswith(ns):
                return False

        # 包含企业相关关键词
        enterprise_suffixes = [
            '集团', '公司', '银行', '保险', '证券', '基金',
            '医院', '大学', '学院', '研究院', '科技', '网络',
            '信息', '互联网', '金融', '地产', '置业', '建设',
            '工程', '制造', '电子', '汽车', '能源', '航空',
            '控股', '协会', '中心', '管理局', '政府', '委员会',
        ]

        for suffix in enterprise_suffixes:
            if suffix in name:
                return True

        return False

    def close(self):
        self.store.close()
