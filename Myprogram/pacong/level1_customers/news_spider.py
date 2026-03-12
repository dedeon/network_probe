"""
第一级爬虫 - 科技媒体/新闻报道爬虫
从36氪、虎嗅、钛媒体等科技媒体中搜索与企业微信/钉钉/飞书相关的报道，
从中提取客户企业名称
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
from utils.search_engine import SearchEngineManager
from utils.ua_pool import ua_pool
from utils.rate_limiter import rate_limiter
from utils.logger import get_logger

logger = get_logger('news_spider')


class NewsSpider:
    """
    科技媒体/新闻报道爬虫
    从科技媒体搜索产品相关报道，提取客户企业名称
    """

    # 科技媒体搜索关键词模板
    SEARCH_TEMPLATES = {
        '企业微信': [
            '"企业微信" 签约 客户 site:36kr.com',
            '"企业微信" 合作 企业 site:huxiu.com',
            '"企业微信" 上线 定制 site:tmtpost.com',
            '"企业微信" 客户 案例 site:sohu.com',
            '"企业微信" 使用 企业 site:zhihu.com',
            '"企业微信" 标杆客户 行业',
        ],
        '钉钉': [
            '"钉钉" 签约 客户 site:36kr.com',
            '"钉钉" 合作 企业 site:huxiu.com',
            '"钉钉" 上线 定制 site:tmtpost.com',
            '"钉钉" 客户 案例 site:sohu.com',
            '"钉钉" 使用 企业 site:zhihu.com',
            '"钉钉" 专属版 定制版 企业',
        ],
        '飞书': [
            '"飞书" 签约 客户 site:36kr.com',
            '"飞书" 合作 企业 site:huxiu.com',
            '"飞书" 上线 site:tmtpost.com',
            '"飞书" 客户 案例 site:sohu.com',
            '"飞书" 使用 企业 site:zhihu.com',
            '"飞书" 标杆客户 签约',
        ],
    }

    # 企业名称提取模式
    ENTERPRISE_PATTERNS = [
        # "XX + 选择/使用/签约/上线/部署 + 产品名" 模式
        re.compile(
            r'([\u4e00-\u9fa5]{2,15}?'
            r'(?:集团|公司|股份|控股|银行|保险|证券|医院|大学|学院'
            r'|研究院|科技|网络|信息|互联网|金融|地产|置业|建设'
            r'|工程|制造|电子|汽车|能源|航空|铁路|通信|传媒))'
        ),
        # "XX省/市/区 + 政务相关" 模式
        re.compile(
            r'([\u4e00-\u9fa5]{2,8}?(?:省|市|区|县|州)'
            r'[\u4e00-\u9fa5]{0,6}?'
            r'(?:政府|管理局|办公厅|委员会|中心))'
        ),
    ]

    # 签约/合作上下文关键词
    CONTEXT_KEYWORDS = [
        '签约', '合作', '选择', '使用', '部署', '上线', '采用',
        '接入', '打造', '携手', '牵手', '达成合作', '战略合作',
        '客户', '服务', '落地', '实施',
    ]

    def __init__(self, customer_db: Optional[CustomerDB] = None):
        self.store = CustomerStore(customer_db)
        self.search_manager = SearchEngineManager()
        from utils.http_client import http_client
        self.http = http_client
        self.total_found = 0
        self._visited_urls: set[str] = set()

    def run(self):
        """执行新闻报道客户挖掘"""
        logger.info("开始科技媒体/新闻报道客户挖掘...")

        for product_line, keywords in self.SEARCH_TEMPLATES.items():
            logger.info(f"--- 产品线: {product_line}, 共 {len(keywords)} 个关键词 ---")

            for keyword in keywords:
                logger.info(f"搜索: {keyword}")

                try:
                    # 搜索
                    results = self.search_manager.search_with_dedup(
                        keyword, num_pages=2
                    )
                    logger.info(f"  获得 {len(results)} 条结果")

                    # 从搜索结果摘要提取
                    snippet_customers = self._extract_from_snippets(
                        results, product_line
                    )
                    if snippet_customers:
                        inserted = self.store.batch_add_customers(snippet_customers)
                        self.total_found += len(snippet_customers)
                        logger.info(f"  从摘要提取 {len(snippet_customers)} 个，新入库 {inserted}")

                    # 爬取文章正文提取
                    article_customers = self._crawl_articles(
                        results, product_line
                    )
                    if article_customers:
                        inserted = self.store.batch_add_customers(article_customers)
                        self.total_found += len(article_customers)
                        logger.info(f"  从文章提取 {len(article_customers)} 个，新入库 {inserted}")

                except Exception as e:
                    logger.error(f"搜索 '{keyword}' 失败: {e}")

                time.sleep(random.uniform(3, 6))

        logger.info(f"新闻报道客户挖掘完成，共发现 {self.total_found} 个客户名")
        self.store.print_stats()

    def _extract_from_snippets(self, results, product_line: str) -> list[dict]:
        """从搜索结果标题+摘要中提取企业名称"""
        customers = []
        seen = set()

        for r in results:
            combined_text = f"{r.title} {r.snippet}"
            names = self._extract_names_with_context(combined_text, product_line)

            for name in names:
                if name not in seen:
                    seen.add(name)
                    customers.append({
                        'enterprise_name': name,
                        'product_line': product_line,
                        'source': f'新闻摘要/{r.source_engine}',
                    })

        return customers

    def _crawl_articles(self, results, product_line: str) -> list[dict]:
        """爬取文章正文，提取企业名称"""
        customers = []
        crawled = 0
        max_crawl = 3  # 每个关键词最多爬取3篇文章

        for r in results:
            if crawled >= max_crawl:
                break

            url = r.url
            if url in self._visited_urls:
                continue

            self._visited_urls.add(url)

            try:
                html = self._fetch_page(url)
                if not html:
                    continue

                article_customers = self._extract_from_article(
                    html, product_line, url
                )
                customers.extend(article_customers)
                crawled += 1

            except Exception as e:
                logger.debug(f"爬取文章失败 {url}: {e}")

            time.sleep(random.uniform(2, 4))

        return customers

    def _extract_from_article(self, html: str, product_line: str,
                              url: str) -> list[dict]:
        """从文章HTML中提取企业名称"""
        soup = BeautifulSoup(html, 'lxml')

        # 移除非正文元素
        for tag in soup(['script', 'style', 'noscript', 'nav', 'footer',
                         'header', 'aside', '.comment', '.sidebar']):
            if hasattr(tag, 'decompose'):
                tag.decompose()

        # 尝试定位正文区域
        article = (
            soup.select_one('article') or
            soup.select_one('.article-content') or
            soup.select_one('.post-content') or
            soup.select_one('.content') or
            soup.select_one('main') or
            soup.body
        )

        if not article:
            return []

        text = article.get_text(separator='\n', strip=True)
        domain = url.split('/')[2] if '/' in url else url

        customers = []
        seen = set()

        # 提取带上下文的企业名
        names = self._extract_names_with_context(text, product_line)
        for name in names:
            if name not in seen:
                seen.add(name)
                customers.append({
                    'enterprise_name': name,
                    'product_line': product_line,
                    'source': f'{domain}/文章',
                })

        return customers

    def _extract_names_with_context(self, text: str, product_line: str) -> list[str]:
        """
        结合上下文提取企业名称
        优先提取在"签约/合作/使用"等关键词附近出现的企业名
        """
        if not text:
            return []

        names = []
        seen = set()

        # 先用正则提取所有候选企业名
        for pattern in self.ENTERPRISE_PATTERNS:
            for match in pattern.finditer(text):
                name = match.group(1).strip()
                if name and name not in seen and len(name) >= 3:
                    # 检查上下文中是否有关键词（前后100字符）
                    start = max(0, match.start() - 100)
                    end = min(len(text), match.end() + 100)
                    context = text[start:end]

                    has_context = any(kw in context for kw in self.CONTEXT_KEYWORDS)
                    # 有上下文关键词或名字本身含企业后缀，都接受
                    if has_context or self._has_enterprise_suffix(name):
                        seen.add(name)
                        names.append(name)

        # 过滤产品名本身
        product_info = PRODUCT_LINES.get(product_line, {})
        product_keywords = product_info.get('name_keywords', [])
        names = [n for n in names if n not in product_keywords]

        return names

    def _has_enterprise_suffix(self, name: str) -> bool:
        """检查名称是否包含企业后缀"""
        suffixes = [
            '集团', '公司', '银行', '保险', '证券', '医院',
            '大学', '学院', '科技', '控股', '管理局', '政府',
        ]
        return any(s in name for s in suffixes)

    def _fetch_page(self, url: str) -> Optional[str]:
        """获取网页（通过统一客户端，自动重试和反爬处理）"""
        return self.http.get_text(url)

    def close(self):
        self.search_manager.close()
        self.store.close()
