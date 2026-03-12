"""
第一级爬虫 - 政务平台爬虫
针对政务类定制包（浙政钉、粤政易、赣政通等），
通过搜索引擎和政务网站爬取政务定制客户信息
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

from config import PRODUCT_LINES, GOV_SEARCH_KEYWORDS
from storage.db import CustomerDB
from level1_customers.customer_store import CustomerStore
from utils.search_engine import SearchEngineManager
from utils.ua_pool import ua_pool
from utils.rate_limiter import rate_limiter
from utils.logger import get_logger

logger = get_logger('gov_spider')


class GovSpider:
    """
    政务平台爬虫
    专门针对政务类定制包的客户信息挖掘：
    1. 用GOV_SEARCH_KEYWORDS中的关键词搜索
    2. 爬取搜索结果中的政务类页面
    3. 提取政务机构名和定制App名称
    """

    # 已知的政务定制包映射（预置种子数据）
    KNOWN_GOV_APPS = [
        {
            'enterprise_name': '浙江省大数据发展管理局',
            'product_line': '钉钉',
            'known_app_name': '浙政钉',
            'industry': '政务',
        },
        {
            'enterprise_name': '广东省政务服务数据管理局',
            'product_line': '钉钉',
            'known_app_name': '粤政易',
            'industry': '政务',
        },
        {
            'enterprise_name': '江西省信息中心',
            'product_line': '钉钉',
            'known_app_name': '赣政通',
            'industry': '政务',
        },
        {
            'enterprise_name': '湖北省政务管理办公室',
            'product_line': '钉钉',
            'known_app_name': '鄂汇办',
            'industry': '政务',
        },
        {
            'enterprise_name': '江苏省大数据管理中心',
            'product_line': '钉钉',
            'known_app_name': '苏政通',
            'industry': '政务',
        },
        {
            'enterprise_name': '河南省大数据管理局',
            'product_line': '钉钉',
            'known_app_name': '豫政通',
            'industry': '政务',
        },
        {
            'enterprise_name': '山东省大数据局',
            'product_line': '钉钉',
            'known_app_name': '鲁政通',
            'industry': '政务',
        },
        {
            'enterprise_name': '福建省数字福建建设领导小组办公室',
            'product_line': '钉钉',
            'known_app_name': '闽政通',
            'industry': '政务',
        },
        {
            'enterprise_name': '安徽省数据资源管理局',
            'product_line': '钉钉',
            'known_app_name': '皖政通',
            'industry': '政务',
        },
    ]

    # 政务机构名称提取正则
    GOV_PATTERNS = [
        # XX省/市/区/县 + 机构后缀
        re.compile(
            r'([\u4e00-\u9fa5]{2,8}?(?:省|市|区|县|州|盟|旗)'
            r'[\u4e00-\u9fa5]{0,10}?'
            r'(?:政府|人民政府|管理局|办公厅|办公室|委员会|中心'
            r'|信息中心|大数据局|大数据管理局|数据资源管理局'
            r'|政务服务局|行政审批局|政务管理办公室|数字化改革办'
            r'|网信办|工信厅|工信局))'
        ),
        # 国家/部委级机构
        re.compile(
            r'([\u4e00-\u9fa5]{2,6}?'
            r'(?:部|委|局|办|院|总局|署))'
        ),
    ]

    # 政务App名称提取正则
    GOV_APP_PATTERNS = [
        # XX政钉/政通/政易/汇办 模式
        re.compile(r'([\u4e00-\u9fa5]{1,4}政(?:钉|通|易|务|办))', re.IGNORECASE),
        re.compile(r'([\u4e00-\u9fa5]{1,4}汇办)', re.IGNORECASE),
        # "XX省/市 + 政务 + App/平台" 模式
        re.compile(
            r'([\u4e00-\u9fa5]{2,4}(?:省|市)?'
            r'[\u4e00-\u9fa5]{0,2}?'
            r'(?:政务(?:钉钉|微信|飞书|App|平台|系统)))'
        ),
        # "XX移动办公" 模式
        re.compile(r'([\u4e00-\u9fa5]{2,6}移动(?:办公|政务)(?:App|平台|系统)?)', re.IGNORECASE),
    ]

    def __init__(self, customer_db: Optional[CustomerDB] = None):
        self.store = CustomerStore(customer_db)
        self.search_manager = SearchEngineManager()
        from utils.http_client import http_client
        self.http = http_client
        self.total_found = 0
        self._visited_urls: set[str] = set()

    def run(self):
        """执行政务平台客户挖掘"""
        logger.info("开始政务平台客户挖掘...")

        # 步骤1: 导入已知的政务种子数据
        self._import_known_gov_apps()

        # 步骤2: 搜索引擎挖掘
        self._search_gov_customers()

        logger.info(f"政务平台客户挖掘完成，共发现 {self.total_found} 条记录")
        self.store.print_stats()

    def _import_known_gov_apps(self):
        """导入已知的政务定制包种子数据"""
        logger.info("导入已知政务定制包种子数据...")

        records = []
        for app in self.KNOWN_GOV_APPS:
            records.append({
                'enterprise_name': app['enterprise_name'],
                'product_line': app['product_line'],
                'source': '政务种子数据',
                'industry': app.get('industry', '政务'),
                'known_app_name': app.get('known_app_name', ''),
            })

        inserted = self.store.batch_add_customers(records)
        self.total_found += inserted
        logger.info(f"种子数据导入完成，新入库 {inserted} 条")

    def _search_gov_customers(self):
        """通过搜索引擎搜索政务类客户"""
        logger.info(f"搜索引擎挖掘政务客户，共 {len(GOV_SEARCH_KEYWORDS)} 个关键词...")

        for keyword in GOV_SEARCH_KEYWORDS:
            logger.info(f"搜索: {keyword}")

            try:
                results = self.search_manager.search_with_dedup(
                    keyword, num_pages=2
                )
                logger.info(f"  获得 {len(results)} 条结果")

                # 从摘要提取
                snippet_customers = self._extract_from_snippets(results, keyword)
                if snippet_customers:
                    inserted = self.store.batch_add_customers(snippet_customers)
                    self.total_found += len(snippet_customers)
                    logger.info(f"  从摘要提取 {len(snippet_customers)} 个，新入库 {inserted}")

                # 爬取gov.cn页面
                gov_customers = self._crawl_gov_pages(results, keyword)
                if gov_customers:
                    inserted = self.store.batch_add_customers(gov_customers)
                    self.total_found += len(gov_customers)
                    logger.info(f"  从政务页提取 {len(gov_customers)} 个，新入库 {inserted}")

            except Exception as e:
                logger.error(f"搜索 '{keyword}' 失败: {e}")

            time.sleep(random.uniform(3, 6))

    def _extract_from_snippets(self, results, keyword: str) -> list[dict]:
        """从搜索结果的标题和摘要中提取政务客户信息"""
        customers = []
        seen = set()

        for r in results:
            combined = f"{r.title} {r.snippet}"

            # 提取政务机构名
            gov_names = self._extract_gov_names(combined)
            # 提取政务App名
            app_names = self._extract_gov_app_names(combined)

            # 确定产品线
            product_line = self._guess_product_line(combined)

            for name in gov_names:
                if name not in seen:
                    seen.add(name)
                    # 查找对应的App名
                    known_app = ''
                    for app_name in app_names:
                        known_app = app_name
                        break

                    customers.append({
                        'enterprise_name': name,
                        'product_line': product_line,
                        'source': f'政务搜索/{r.source_engine}',
                        'industry': '政务',
                        'known_app_name': known_app,
                    })

            # 如果只发现了App名，也记录
            for app_name in app_names:
                if app_name not in seen:
                    seen.add(app_name)
                    customers.append({
                        'enterprise_name': app_name,
                        'product_line': product_line,
                        'source': f'政务搜索/{r.source_engine}',
                        'industry': '政务',
                        'known_app_name': app_name,
                    })

        return customers

    def _crawl_gov_pages(self, results, keyword: str) -> list[dict]:
        """爬取搜索结果中的政务类页面"""
        customers = []
        crawled = 0
        max_crawl = 3

        for r in results:
            if crawled >= max_crawl:
                break

            url = r.url
            if url in self._visited_urls:
                continue

            # 优先爬取gov.cn域名
            is_gov = 'gov.cn' in url.lower()
            if not is_gov and crawled >= 1:
                continue  # 非政府域名最多爬1个

            self._visited_urls.add(url)

            try:
                html = self._fetch_page(url)
                if not html:
                    continue

                page_customers = self._extract_from_gov_page(html, url)
                customers.extend(page_customers)
                crawled += 1

            except Exception as e:
                logger.debug(f"爬取政务页失败 {url}: {e}")

            time.sleep(random.uniform(2, 4))

        return customers

    def _extract_from_gov_page(self, html: str, url: str) -> list[dict]:
        """从政务页面中提取客户信息"""
        soup = BeautifulSoup(html, 'lxml')

        # 移除无关元素
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()

        text = soup.get_text(separator='\n', strip=True)
        domain = url.split('/')[2] if '/' in url else url

        customers = []
        seen = set()

        product_line = self._guess_product_line(text)

        # 提取政务机构名
        gov_names = self._extract_gov_names(text)
        app_names = self._extract_gov_app_names(text)

        for name in gov_names:
            if name not in seen:
                seen.add(name)
                known_app = ''
                for an in app_names:
                    known_app = an
                    break

                customers.append({
                    'enterprise_name': name,
                    'product_line': product_line,
                    'source': f'{domain}/政务页面',
                    'industry': '政务',
                    'known_app_name': known_app,
                })

        for app_name in app_names:
            if app_name not in seen:
                seen.add(app_name)
                customers.append({
                    'enterprise_name': app_name,
                    'product_line': product_line,
                    'source': f'{domain}/政务页面',
                    'industry': '政务',
                    'known_app_name': app_name,
                })

        return customers

    def _extract_gov_names(self, text: str) -> list[str]:
        """从文本中提取政务机构名称"""
        names = []
        seen = set()

        for pattern in self.GOV_PATTERNS:
            for match in pattern.finditer(text):
                name = match.group(1).strip()
                if name and name not in seen and len(name) >= 4:
                    # 过滤太泛的匹配
                    if not self._is_too_generic_gov(name):
                        seen.add(name)
                        names.append(name)

        return names

    def _extract_gov_app_names(self, text: str) -> list[str]:
        """从文本中提取政务App名称"""
        names = []
        seen = set()

        for pattern in self.GOV_APP_PATTERNS:
            for match in pattern.finditer(text):
                name = match.group(1).strip()
                if name and name not in seen and len(name) >= 2:
                    seen.add(name)
                    names.append(name)

        return names

    def _guess_product_line(self, text: str) -> str:
        """根据文本内容猜测产品线"""
        text_lower = text.lower()

        scores = {'企业微信': 0, '钉钉': 0, '飞书': 0}

        for pl, info in PRODUCT_LINES.items():
            for kw in info.get('name_keywords', []):
                if kw.lower() in text_lower:
                    scores[pl] += 1

        # 返回得分最高的
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best

        return '钉钉'  # 政务类默认为钉钉（政务钉钉最多）

    def _is_too_generic_gov(self, name: str) -> bool:
        """检查政务机构名是否过于宽泛"""
        too_generic = [
            '政府', '国务院', '人大', '政协',
            '中央', '全国', '国家',
        ]
        return name in too_generic or len(name) < 4

    def _fetch_page(self, url: str) -> Optional[str]:
        """获取网页（通过统一客户端，自动重试和反爬处理）"""
        return self.http.get_text(url)

    def close(self):
        self.search_manager.close()
        self.store.close()
