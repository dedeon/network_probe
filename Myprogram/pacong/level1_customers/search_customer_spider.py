"""
第一级爬虫 - 搜索引擎客户名称挖掘
通过搜索引擎搜索公开报道和文章，批量提取使用企业微信/钉钉/飞书的客户企业名称
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

from config import PRODUCT_LINES, LEVEL1_SEARCH_KEYWORDS
from storage.db import CustomerDB
from level1_customers.customer_store import CustomerStore
from utils.search_engine import SearchEngineManager, SearchResult
from utils.ua_pool import ua_pool
from utils.rate_limiter import rate_limiter
from utils.logger import get_logger

logger = get_logger('search_customer_spider')


class SearchCustomerSpider:
    """
    搜索引擎客户名称挖掘爬虫
    1. 用预定义关键词在搜索引擎中搜索
    2. 解析搜索结果标题和摘要，提取企业名称
    3. 对搜索结果页面进行二次爬取，提取更多企业名
    """

    # 从搜索结果的标题/摘要中提取企业名称的正则
    ENTERPRISE_PATTERNS = [
        # "XX集团/公司/银行等 + 选择/使用/签约/上线 + 产品名" 模式
        re.compile(
            r'([\u4e00-\u9fa5]{2,20}?'
            r'(?:集团|公司|股份|控股|银行|保险|证券|医院|大学|学院'
            r'|研究院|科技|网络|信息|互联网|金融|地产|置业|建设'
            r'|工程|制造|电子|汽车|能源|航空|铁路|通信|传媒'
            r'|电力|矿业|物流|酒店|商业|管理局|中心|委员会))'
        ),
    ]

    # 结果页面中提取客户列表的选择器
    CUSTOMER_LIST_SELECTORS = [
        # 文章中的客户列表
        'article li', 'article p',
        '.article-content li', '.article-content p',
        '.post-content li', '.post-content p',
        '.content li', '.content p',
        # 表格中的客户
        'table td',
    ]

    # 需要进行二次爬取的域名（高价值来源）
    HIGH_VALUE_DOMAINS = [
        '36kr.com', 'zhihu.com', 'sohu.com', '163.com',
        'sina.com.cn', 'qq.com', 'baidu.com',
        'csdn.net', 'jianshu.com', 'sspai.com',
        'tmtpost.com', 'huxiu.com', 'leiphone.com',
        'work.weixin.qq.com', 'dingtalk.com', 'feishu.cn',
    ]

    def __init__(self, customer_db: Optional[CustomerDB] = None):
        self.store = CustomerStore(customer_db)
        self.search_manager = SearchEngineManager()
        from utils.http_client import http_client
        self.http = http_client
        self.total_found = 0
        self._visited_urls: set[str] = set()

    def run(self):
        """执行搜索引擎客户挖掘"""
        logger.info("开始搜索引擎客户名称挖掘...")

        for product_line, keywords in LEVEL1_SEARCH_KEYWORDS.items():
            logger.info(f"--- 产品线: {product_line}, 共 {len(keywords)} 个关键词 ---")

            for keyword in keywords:
                logger.info(f"搜索关键词: {keyword}")

                try:
                    # 步骤1: 搜索
                    results = self.search_manager.search_with_dedup(
                        keyword, num_pages=2
                    )
                    logger.info(f"  获得 {len(results)} 条搜索结果")

                    # 步骤2: 从搜索结果的标题和摘要中提取企业名
                    snippet_customers = self._extract_from_snippets(
                        results, product_line, keyword
                    )
                    if snippet_customers:
                        inserted = self.store.batch_add_customers(snippet_customers)
                        self.total_found += len(snippet_customers)
                        logger.info(f"  从摘要中提取 {len(snippet_customers)} 个客户名，新入库 {inserted}")

                    # 步骤3: 对高价值页面进行二次爬取
                    page_customers = self._crawl_result_pages(
                        results, product_line, keyword
                    )
                    if page_customers:
                        inserted = self.store.batch_add_customers(page_customers)
                        self.total_found += len(page_customers)
                        logger.info(f"  从结果页提取 {len(page_customers)} 个客户名，新入库 {inserted}")

                except Exception as e:
                    logger.error(f"搜索关键词 '{keyword}' 失败: {e}")

                # 关键词之间的间隔
                time.sleep(random.uniform(2, 5))

        logger.info(f"搜索引擎客户挖掘完成，共发现 {self.total_found} 个客户名")
        self.store.print_stats()

    def _extract_from_snippets(self, results: list[SearchResult],
                               product_line: str,
                               keyword: str) -> list[dict]:
        """从搜索结果的标题和摘要中提取企业名称"""
        customers = []
        seen = set()

        for result in results:
            # 从标题提取
            names_from_title = self._extract_enterprise_names(result.title)
            # 从摘要提取
            names_from_snippet = self._extract_enterprise_names(result.snippet)

            all_names = names_from_title + names_from_snippet

            for name in all_names:
                if name not in seen and self._is_likely_customer(name, product_line):
                    seen.add(name)
                    customers.append({
                        'enterprise_name': name,
                        'product_line': product_line,
                        'source': f'搜索引擎/{result.source_engine}/{keyword[:20]}',
                    })

        return customers

    def _crawl_result_pages(self, results: list[SearchResult],
                            product_line: str,
                            keyword: str) -> list[dict]:
        """对搜索结果中的高价值页面进行二次爬取"""
        customers = []
        crawled_count = 0
        max_crawl = 5  # 每个关键词最多二次爬取5个页面

        for result in results:
            if crawled_count >= max_crawl:
                break

            url = result.url
            if url in self._visited_urls:
                continue

            # 只爬取高价值域名
            if not self._is_high_value_url(url):
                continue

            self._visited_urls.add(url)

            try:
                html = self._fetch_page(url)
                if not html:
                    continue

                page_customers = self._extract_from_page(
                    html, product_line, url, keyword
                )
                customers.extend(page_customers)
                crawled_count += 1

            except Exception as e:
                logger.debug(f"二次爬取失败 {url}: {e}")

            time.sleep(random.uniform(2, 4))

        return customers

    def _extract_from_page(self, html: str, product_line: str,
                           url: str, keyword: str) -> list[dict]:
        """从页面HTML中提取企业名称"""
        soup = BeautifulSoup(html, 'lxml')

        # 移除无关元素
        for tag in soup(['script', 'style', 'noscript', 'nav', 'footer', 'header']):
            tag.decompose()

        customers = []
        seen = set()

        # 方式1: 从文章正文中提取
        text = soup.get_text(separator='\n', strip=True)
        names = self._extract_enterprise_names(text)

        domain = url.split('/')[2] if '/' in url else url

        for name in names:
            if name not in seen and self._is_likely_customer(name, product_line):
                seen.add(name)
                customers.append({
                    'enterprise_name': name,
                    'product_line': product_line,
                    'source': f'{domain}/文章提取',
                })

        # 方式2: 从列表、表格等结构化元素中提取
        for selector in self.CUSTOMER_LIST_SELECTORS:
            for elem in soup.select(selector)[:100]:  # 限制数量
                elem_text = elem.get_text(strip=True)
                if not elem_text or len(elem_text) > 200:
                    continue

                elem_names = self._extract_enterprise_names(elem_text)
                for name in elem_names:
                    if name not in seen and self._is_likely_customer(name, product_line):
                        seen.add(name)
                        customers.append({
                            'enterprise_name': name,
                            'product_line': product_line,
                            'source': f'{domain}/列表提取',
                        })

        return customers

    def _extract_enterprise_names(self, text: str) -> list[str]:
        """从文本中用正则提取企业名称"""
        if not text:
            return []

        names = []
        seen = set()

        for pattern in self.ENTERPRISE_PATTERNS:
            for match in pattern.finditer(text):
                name = match.group(1).strip()
                if name and name not in seen and len(name) >= 3:
                    seen.add(name)
                    names.append(name)

        return names

    def _is_likely_customer(self, name: str, product_line: str) -> bool:
        """判断名称是否可能是客户企业名"""
        if not name or len(name) < 3 or len(name) > 30:
            return False

        # 过滤产品名本身
        product_info = PRODUCT_LINES.get(product_line, {})
        for kw in product_info.get('name_keywords', []):
            if name == kw:
                return False

        # 过滤常见噪声词
        noise_words = [
            '客户案例', '成功案例', '合作企业', '使用案例', '行业方案',
            '搜索结果', '百度知道', '知乎问答', '相关推荐', '热门文章',
            '版权所有', '联系我们', '关于我们', '隐私政策', '用户协议',
        ]
        for noise in noise_words:
            if name == noise:
                return False

        return True

    def _is_high_value_url(self, url: str) -> bool:
        """判断URL是否属于高价值来源"""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            for hv_domain in self.HIGH_VALUE_DOMAINS:
                if hv_domain in domain:
                    return True
        except Exception:
            pass
        return False

    def _fetch_page(self, url: str) -> Optional[str]:
        """获取网页内容（通过统一客户端，自动重试和反爬处理）"""
        return self.http.get_text(url)

    def close(self):
        self.search_manager.close()
        self.store.close()
