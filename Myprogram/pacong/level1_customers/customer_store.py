"""
客户名称存储管理模块
封装 CustomerDB，提供客户记录的去重写入、批量导入和统计功能
"""
import re
from typing import Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PRODUCT_LINES
from storage.db import CustomerDB
from utils.logger import get_logger

logger = get_logger('customer_store')


class CustomerStore:
    """
    客户名称存储管理器
    - 统一的客户写入入口，自动去重
    - 企业名称清洗与规范化
    - 按产品线/来源统计
    """

    # 无效企业名过滤规则
    _INVALID_PATTERNS = [
        re.compile(r'^[\d\s\-_\.]+$'),              # 纯数字/符号
        re.compile(r'^.{0,2}$'),                      # 过短（<=2字符）
        re.compile(r'^(测试|demo|test|admin|sample)', re.IGNORECASE),
        re.compile(r'^(企业微信|钉钉|飞书|DingTalk|WeCom|Lark|Feishu)$', re.IGNORECASE),
        # 过滤明显不是企业名的文本片段
        re.compile(r'^(如何|怎么|为什么|什么|可以|支持|帮助|揭秘|谁给|满足|适配|让|将|通过|等|的)'),
        re.compile(r'(信息|功能|服务|中心|数据|方案|产品|下载|注册|登录)$'),
        re.compile(r'^[\u4e00-\u9fa5]{2,3}(的|了|着|过|中|里|内)'),
        re.compile(r'(怎么|如何|为何|能否|是否|可否)'),
    ]

    # 必须包含企业名特征词才算有效
    _ENTERPRISE_SUFFIXES = {
        '集团', '公司', '股份', '控股', '银行', '保险', '证券', '基金',
        '医院', '大学', '学院', '研究院', '研究所', '科技', '网络',
        '信息', '互联网', '金融', '地产', '置业', '建设', '工程',
        '制造', '电子', '汽车', '能源', '航空', '铁路', '通信',
        '传媒', '电力', '物流', '酒店', '餐饮', '协会', '管理局',
        '政府', '委员会', '厅', '局', '办', '院', '部',
    }

    # 企业名称清洗：去掉常见后缀噪声
    _CLEAN_SUFFIXES = [
        '有限公司', '股份有限公司', '有限责任公司',
        '集团公司', '总公司', '分公司',
    ]

    def __init__(self, db: Optional[CustomerDB] = None):
        self.db = db or CustomerDB()
        self._seen_cache: set[str] = set()
        self._load_cache()

    def _load_cache(self):
        """加载已有客户名到内存缓存"""
        try:
            names = self.db.get_customer_names()
            self._seen_cache = set(names)
            logger.info(f"加载客户缓存: {len(self._seen_cache)} 条")
        except Exception as e:
            logger.warning(f"加载客户缓存失败: {e}")

    def add_customer(self, enterprise_name: str, product_line: str,
                     source: str, industry: str = '',
                     known_app_name: str = '') -> bool:
        """
        添加一条客户记录（自动去重+清洗）
        Returns:
            True 表示新插入，False 表示已存在或无效
        """
        # 清洗企业名称
        cleaned = self._clean_name(enterprise_name)
        if not cleaned:
            return False

        # 验证企业名有效性
        if not self._is_valid_name(cleaned):
            logger.debug(f"跳过无效企业名: '{enterprise_name}'")
            return False

        # 验证产品线
        if product_line not in PRODUCT_LINES:
            logger.warning(f"未知产品线: {product_line}")
            return False

        # 内存去重
        cache_key = f"{cleaned}|{product_line}"
        if cache_key in self._seen_cache:
            return False

        # 写入数据库
        inserted = self.db.insert_customer(
            enterprise_name=cleaned,
            product_line=product_line,
            source=source,
            industry=industry,
            known_app_name=known_app_name,
        )

        if inserted:
            self._seen_cache.add(cache_key)
            logger.debug(f"新客户: {cleaned} ({product_line}) from {source}")

        return inserted

    def batch_add_customers(self, records: list[dict]) -> int:
        """
        批量添加客户记录
        records: [{'enterprise_name', 'product_line', 'source', 'industry'?, 'known_app_name'?}]
        Returns:
            新插入的条数
        """
        valid_records = []
        for r in records:
            cleaned = self._clean_name(r.get('enterprise_name', ''))
            if not cleaned or not self._is_valid_name(cleaned):
                continue

            product_line = r.get('product_line', '')
            if product_line not in PRODUCT_LINES:
                continue

            cache_key = f"{cleaned}|{product_line}"
            if cache_key in self._seen_cache:
                continue

            valid_records.append({
                'enterprise_name': cleaned,
                'product_line': product_line,
                'source': r.get('source', ''),
                'industry': r.get('industry', ''),
                'known_app_name': r.get('known_app_name', ''),
            })

        if not valid_records:
            return 0

        inserted = self.db.batch_insert_customers(valid_records)

        # 更新缓存
        for r in valid_records:
            cache_key = f"{r['enterprise_name']}|{r['product_line']}"
            self._seen_cache.add(cache_key)

        logger.info(f"批量写入 {inserted}/{len(valid_records)} 条客户记录")
        return inserted

    def _clean_name(self, name: str) -> str:
        """清洗企业名称"""
        if not name:
            return ''

        # 去掉前后空白和特殊字符
        cleaned = name.strip()
        cleaned = re.sub(r'[\r\n\t]+', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)

        # 去掉引号
        cleaned = cleaned.strip('"\'""''「」【】')

        # 去掉 HTML 标签残留
        cleaned = re.sub(r'<[^>]+>', '', cleaned)

        return cleaned.strip()

    def _is_valid_name(self, name: str) -> bool:
        """验证企业名称是否有效"""
        if not name or len(name) < 3:
            return False

        # 过滤无效模式
        for pattern in self._INVALID_PATTERNS:
            if pattern.search(name):
                return False

        # 过滤过长名称（可能是误提取的段落）
        if len(name) > 30:
            return False

        # 必须包含至少一个企业名特征后缀词
        has_suffix = False
        for suffix in self._ENTERPRISE_SUFFIXES:
            if suffix in name:
                has_suffix = True
                break
        if not has_suffix:
            return False

        # 排除纯通用描述词（没有实际企业名前缀）
        generic_only = [
            '帮助中心', '开发者中心', '数据中心', '服务中心',
            '传统制造', '众多政府', '餐饮集团', '的酒店集团',
        ]
        if name in generic_only:
            return False

        return True

    def get_stats(self) -> dict:
        """获取客户统计信息"""
        all_customers = self.db.get_all_customers()
        stats = {
            'total': len(all_customers),
            'by_product_line': {},
            'by_source': {},
            'by_industry': {},
        }

        for c in all_customers:
            pl = c.get('product_line', '未知')
            stats['by_product_line'][pl] = stats['by_product_line'].get(pl, 0) + 1

            src = c.get('source', '未知')
            # 提取来源域名
            if '/' in src:
                src = src.split('/')[0] if '.' in src.split('/')[0] else src
            stats['by_source'][src] = stats['by_source'].get(src, 0) + 1

            ind = c.get('industry', '') or '未分类'
            stats['by_industry'][ind] = stats['by_industry'].get(ind, 0) + 1

        return stats

    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()
        logger.info(f"客户总数: {stats['total']}")
        logger.info("按产品线:")
        for pl, cnt in stats['by_product_line'].items():
            logger.info(f"  {pl}: {cnt}")
        logger.info("按来源:")
        for src, cnt in sorted(stats['by_source'].items(), key=lambda x: -x[1])[:10]:
            logger.info(f"  {src}: {cnt}")

    def close(self):
        self.db.close()
