"""
数据去重模块
基于包名+来源的精确去重 + 模糊去重（相似包名/应用名合并）
"""
import hashlib
import logging
import re
from collections import defaultdict
from typing import Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.db import AppInfoDB

logger = logging.getLogger('crawler.pipeline.dedup')


class BloomFilter:
    """简易 Bloom Filter，用于快速判重"""

    def __init__(self, capacity: int = 100000, error_rate: float = 0.001):
        import math
        self.size = int(-capacity * math.log(error_rate) / (math.log(2) ** 2))
        self.hash_count = int(self.size / capacity * math.log(2))
        self.bit_array = bytearray(self.size // 8 + 1)

    def _hashes(self, item: str):
        h1 = int(hashlib.md5(item.encode()).hexdigest(), 16)
        h2 = int(hashlib.sha1(item.encode()).hexdigest(), 16)
        for i in range(self.hash_count):
            yield (h1 + i * h2) % self.size

    def add(self, item: str):
        for pos in self._hashes(item):
            self.bit_array[pos // 8] |= (1 << (pos % 8))

    def __contains__(self, item: str) -> bool:
        return all(
            self.bit_array[pos // 8] & (1 << (pos % 8))
            for pos in self._hashes(item)
        )


class Deduplicator:
    """
    数据去重处理器

    策略：
    1. 精确去重：相同 package_name + source_site 仅保留一条（DB UNIQUE约束已处理）
    2. 跨源去重：同一 package_name 来自不同 source_site，保留全部但标记多源验证
    3. 模糊去重：相似包名合并（如 com.tencent.wework.abc 和 com.tencent.wework.abc.debug）
    4. 无效记录清除：删除缺少关键字段的记录
    """

    def __init__(self, db: AppInfoDB):
        self.db = db
        self.bloom = BloomFilter()
        self.stats = {
            'total_before': 0,
            'invalid_removed': 0,
            'debug_removed': 0,
            'duplicate_merged': 0,
            'total_after': 0,
        }

    def run(self):
        """执行去重处理"""
        apps = self.db.get_all_apps()
        self.stats['total_before'] = len(apps)
        logger.info(f"去重处理开始，当前共 {len(apps)} 条记录")

        # 阶段1：清除无效记录
        self._remove_invalid(apps)

        # 阶段2：清除调试/测试包
        apps = self.db.get_all_apps()
        self._remove_debug_packages(apps)

        # 阶段3：跨源合并标记
        apps = self.db.get_all_apps()
        self._mark_cross_source(apps)

        # 阶段4：模糊去重 - 相似包名合并
        apps = self.db.get_all_apps()
        self._merge_similar(apps)

        self.stats['total_after'] = self.db.count()
        logger.info(
            f"去重完成: {self.stats['total_before']} → {self.stats['total_after']} 条 "
            f"(无效删除{self.stats['invalid_removed']}, "
            f"调试包删除{self.stats['debug_removed']}, "
            f"相似合并{self.stats['duplicate_merged']})"
        )

    def _remove_invalid(self, apps: list[dict]):
        """移除缺少关键字段的无效记录"""
        conn = self.db._get_conn()
        removed = 0
        for app in apps:
            pkg = (app.get('package_name') or '').strip()
            name = (app.get('app_name') or '').strip()
            url = (app.get('source_url') or '').strip()

            if not pkg or not name:
                try:
                    conn.execute(
                        'DELETE FROM app_info WHERE id = ?', (app['id'],)
                    )
                    removed += 1
                except Exception:
                    pass

            # 包名格式校验：至少两段以点号分隔
            elif pkg and not re.match(r'^[a-zA-Z][a-zA-Z0-9]*(\.[a-zA-Z0-9_]+)+$', pkg):
                try:
                    conn.execute(
                        'DELETE FROM app_info WHERE id = ?', (app['id'],)
                    )
                    removed += 1
                except Exception:
                    pass

        conn.commit()
        self.stats['invalid_removed'] = removed
        if removed:
            logger.info(f"清除 {removed} 条无效记录")

    def _remove_debug_packages(self, apps: list[dict]):
        """移除调试/测试包"""
        debug_patterns = [
            re.compile(r'\.debug$', re.IGNORECASE),
            re.compile(r'\.test$', re.IGNORECASE),
            re.compile(r'\.dev$', re.IGNORECASE),
            re.compile(r'\.staging$', re.IGNORECASE),
            re.compile(r'\.beta$', re.IGNORECASE),
            re.compile(r'\.internal$', re.IGNORECASE),
        ]

        conn = self.db._get_conn()
        removed = 0
        for app in apps:
            pkg = app.get('package_name', '')
            if any(p.search(pkg) for p in debug_patterns):
                try:
                    conn.execute(
                        'DELETE FROM app_info WHERE id = ?', (app['id'],)
                    )
                    removed += 1
                except Exception:
                    pass

        conn.commit()
        self.stats['debug_removed'] = removed
        if removed:
            logger.info(f"清除 {removed} 条调试/测试包记录")

    def _mark_cross_source(self, apps: list[dict]):
        """标记多源验证：同一包名在多个来源出现"""
        pkg_sources = defaultdict(list)
        for app in apps:
            pkg_sources[app['package_name']].append(app)

        conn = self.db._get_conn()
        for pkg, group in pkg_sources.items():
            if len(group) > 1:
                sources = list({a['source_site'] for a in group})
                if len(sources) > 1:
                    # 在描述字段追加多源验证信息
                    verify_note = f"[多源验证: {', '.join(sorted(sources))}]"
                    for a in group:
                        desc = a.get('description', '') or ''
                        if '多源验证' not in desc:
                            new_desc = f"{desc} {verify_note}".strip()
                            try:
                                conn.execute(
                                    'UPDATE app_info SET description = ? WHERE id = ?',
                                    (new_desc, a['id'])
                                )
                            except Exception:
                                pass
        conn.commit()

    def _merge_similar(self, apps: list[dict]):
        """
        模糊去重：对于同一基础包名的变体，保留信息最完整的记录。
        例如 com.tencent.wework.abc 和 com.tencent.wework.abc.xxx
        只对明确的变体关系进行合并。
        """
        # 按基础包名分组（取前三段）
        base_groups = defaultdict(list)
        for app in apps:
            pkg = app.get('package_name', '')
            parts = pkg.split('.')
            base = '.'.join(parts[:3]) if len(parts) >= 3 else pkg
            base_groups[base].append(app)

        conn = self.db._get_conn()
        merged = 0
        for base, group in base_groups.items():
            if len(group) <= 1:
                continue

            # 按 (package_name, source_site) 分组，同一source_site下的相同包名已由DB约束去重
            # 这里处理同一source_site下不同但高度相似的包名
            by_source = defaultdict(list)
            for a in group:
                by_source[a['source_site']].append(a)

            for source, src_apps in by_source.items():
                if len(src_apps) <= 1:
                    continue

                # 同一来源下，如果存在 "pkg" 和 "pkg.xxx" 的关系
                # 且 xxx 是常见后缀，则视为变体
                pkg_map = {a['package_name']: a for a in src_apps}
                to_remove = set()

                for pkg1 in pkg_map:
                    for pkg2 in pkg_map:
                        if pkg1 == pkg2 or pkg2 in to_remove:
                            continue
                        # pkg2 是 pkg1 的子包变体
                        if pkg2.startswith(pkg1 + '.'):
                            suffix = pkg2[len(pkg1) + 1:]
                            # 仅合并明确的变体后缀
                            variant_suffixes = {
                                'hd', 'lite', 'pro', 'tablet', 'pad',
                                'samsung', 'huawei', 'xiaomi',
                            }
                            if suffix.lower() in variant_suffixes:
                                # 保留主包，删除变体
                                to_remove.add(pkg2)

                for pkg in to_remove:
                    app = pkg_map[pkg]
                    try:
                        conn.execute(
                            'DELETE FROM app_info WHERE id = ?', (app['id'],)
                        )
                        merged += 1
                    except Exception:
                        pass

        conn.commit()
        self.stats['duplicate_merged'] = merged
        if merged:
            logger.info(f"合并 {merged} 条相似变体记录")
