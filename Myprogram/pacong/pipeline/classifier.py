"""
产品线分类模块
将应用准确归类到企业微信/钉钉/飞书产品线
"""
import logging
import re
from typing import Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.db import AppInfoDB
from config import PRODUCT_LINES

logger = logging.getLogger('crawler.pipeline.classifier')


class ProductClassifier:
    """
    产品线分类处理器

    分类策略（优先级从高到低）：
    1. 包名精确匹配：按 PRODUCT_LINES 中的 package_patterns
    2. 应用名关键词匹配：按 name_keywords
    3. 描述文本分析：按关键词密度
    4. 开发者归属推断
    """

    # 开发者→产品线映射
    DEVELOPER_PRODUCT_MAP = {
        '腾讯': '企业微信',
        'tencent': '企业微信',
        '深圳市腾讯': '企业微信',
        '阿里巴巴': '钉钉',
        'alibaba': '钉钉',
        '钉钉': '钉钉',
        'dingtalk': '钉钉',
        '字节跳动': '飞书',
        'bytedance': '飞书',
        '飞书': '飞书',
        'lark': '飞书',
    }

    def __init__(self, db: AppInfoDB):
        self.db = db
        self.stats = {
            'total': 0,
            'reclassified': 0,
            'by_package': 0,
            'by_name': 0,
            'by_description': 0,
            'by_developer': 0,
            'unchanged': 0,
        }

    def run(self):
        """执行产品线分类"""
        apps = self.db.get_all_apps()
        self.stats['total'] = len(apps)
        logger.info(f"产品线分类开始，共 {len(apps)} 条记录")

        conn = self.db._get_conn()

        for app in apps:
            current_line = app.get('product_line', '').strip()
            new_line = self._classify(app)

            if not new_line:
                self.stats['unchanged'] += 1
                continue

            if new_line != current_line:
                try:
                    conn.execute(
                        'UPDATE app_info SET product_line = ? WHERE id = ?',
                        (new_line, app['id'])
                    )
                    self.stats['reclassified'] += 1
                except Exception as e:
                    logger.debug(f"分类更新失败 (id={app['id']}): {e}")
            else:
                self.stats['unchanged'] += 1

        conn.commit()

        logger.info(
            f"产品线分类完成: "
            f"包名匹配{self.stats['by_package']}, "
            f"名称匹配{self.stats['by_name']}, "
            f"描述匹配{self.stats['by_description']}, "
            f"开发者推断{self.stats['by_developer']}, "
            f"重分类{self.stats['reclassified']}, "
            f"未变{self.stats['unchanged']}"
        )

    def _classify(self, app: dict) -> Optional[str]:
        """按优先级对应用进行分类"""
        pkg = app.get('package_name', '')
        name = app.get('app_name', '')
        desc = app.get('description', '')
        dev = app.get('developer', '')

        # 1. 包名精确匹配（最高优先级）
        result = self._classify_by_package(pkg)
        if result:
            self.stats['by_package'] += 1
            return result

        # 2. 应用名关键词匹配
        result = self._classify_by_name(name)
        if result:
            self.stats['by_name'] += 1
            return result

        # 3. 开发者归属推断
        result = self._classify_by_developer(dev)
        if result:
            self.stats['by_developer'] += 1
            return result

        # 4. 描述文本分析
        result = self._classify_by_description(desc)
        if result:
            self.stats['by_description'] += 1
            return result

        return None

    def _classify_by_package(self, package_name: str) -> Optional[str]:
        """通过包名模式匹配分类"""
        if not package_name:
            return None

        for product_line, config in PRODUCT_LINES.items():
            for pattern in config['package_patterns']:
                if pattern.match(package_name):
                    return product_line

        return None

    def _classify_by_name(self, app_name: str) -> Optional[str]:
        """通过应用名关键词匹配分类"""
        if not app_name:
            return None

        name_lower = app_name.lower()
        scores = {}

        for product_line, config in PRODUCT_LINES.items():
            score = 0
            for keyword in config['name_keywords']:
                kw_lower = keyword.lower()
                if kw_lower in name_lower:
                    # 完全匹配得分更高
                    if name_lower == kw_lower:
                        score += 10
                    elif name_lower.startswith(kw_lower):
                        score += 5
                    else:
                        score += 3
            if score > 0:
                scores[product_line] = score

        if scores:
            return max(scores, key=scores.get)

        return None

    def _classify_by_developer(self, developer: str) -> Optional[str]:
        """通过开发者归属推断分类"""
        if not developer:
            return None

        dev_lower = developer.lower()

        for dev_key, product_line in self.DEVELOPER_PRODUCT_MAP.items():
            if dev_key.lower() in dev_lower:
                return product_line

        return None

    def _classify_by_description(self, description: str) -> Optional[str]:
        """通过描述文本关键词密度分析分类"""
        if not description or len(description) < 20:
            return None

        desc_lower = description.lower()
        scores = {}

        for product_line, config in PRODUCT_LINES.items():
            score = 0
            for keyword in config['name_keywords']:
                kw_lower = keyword.lower()
                # 计算出现次数
                count = desc_lower.count(kw_lower)
                score += count * 2

            # 包名模式也检查（有些描述中会提到包名）
            for pattern in config['package_patterns']:
                if pattern.search(description):
                    score += 3

            if score > 0:
                scores[product_line] = score

        if scores:
            best = max(scores, key=scores.get)
            # 至少要有2分以上的置信度
            if scores[best] >= 2:
                return best

        return None

    @staticmethod
    def is_custom_package(package_name: str) -> bool:
        """
        判断是否为定制包（非官方标准包）。
        供外部模块调用的静态方法。
        """
        if not package_name:
            return False

        official_packages = set()
        for config in PRODUCT_LINES.values():
            official_packages.add(config['official_package'])

        # 如果是官方标准包名则不是定制包
        if package_name in official_packages:
            return False

        # 如果匹配产品线模式且不是官方包名，则是定制包
        for config in PRODUCT_LINES.values():
            for pattern in config['package_patterns']:
                if pattern.match(package_name):
                    return True

        return False
