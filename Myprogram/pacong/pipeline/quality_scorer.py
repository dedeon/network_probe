"""
数据质量评分模块
根据字段完整度和多源验证为每条记录计算质量分
"""
import logging
from collections import defaultdict
from typing import Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.db import AppInfoDB
from config import QUALITY_WEIGHTS

logger = logging.getLogger('crawler.pipeline.quality_scorer')


class QualityScorer:
    """
    数据质量评分处理器

    评分维度（来自 config.QUALITY_WEIGHTS）：
    - has_package_name:       0.25  包名存在
    - has_app_name:           0.15  应用名存在
    - has_enterprise_name:    0.15  企业名已提取
    - has_version:            0.10  版本号存在
    - has_developer:          0.10  开发者存在
    - has_description:        0.05  描述存在
    - has_download_count:     0.05  下载量存在
    - multi_source_verified:  0.15  多源验证

    总分 0.0 ~ 1.0
    """

    # 评分等级
    GRADE_THRESHOLDS = {
        'A': 0.80,  # 高质量
        'B': 0.60,  # 中等质量
        'C': 0.40,  # 基本可用
        'D': 0.20,  # 低质量
        'F': 0.00,  # 极低质量
    }

    def __init__(self, db: AppInfoDB):
        self.db = db
        self.weights = QUALITY_WEIGHTS
        self.stats = {
            'total': 0,
            'updated': 0,
            'grade_distribution': defaultdict(int),
            'avg_score': 0.0,
        }

    def run(self):
        """执行质量评分"""
        apps = self.db.get_all_apps()
        self.stats['total'] = len(apps)
        logger.info(f"质量评分开始，共 {len(apps)} 条记录")

        if not apps:
            logger.info("无记录可评分")
            return

        # 预计算多源验证信息
        multi_source_pkgs = self._get_multi_source_packages(apps)

        conn = self.db._get_conn()
        total_score = 0.0

        for app in apps:
            score = self._calculate_score(app, multi_source_pkgs)
            grade = self._get_grade(score)
            self.stats['grade_distribution'][grade] += 1
            total_score += score

            # 如果评分有变化才更新
            old_score = app.get('quality_score', 0.0) or 0.0
            if abs(score - old_score) > 0.001:
                try:
                    conn.execute(
                        'UPDATE app_info SET quality_score = ? WHERE id = ?',
                        (round(score, 4), app['id'])
                    )
                    self.stats['updated'] += 1
                except Exception as e:
                    logger.debug(f"评分更新失败 (id={app['id']}): {e}")

        conn.commit()

        self.stats['avg_score'] = total_score / len(apps) if apps else 0

        # 输出统计
        logger.info(
            f"质量评分完成: 平均分 {self.stats['avg_score']:.2f}, "
            f"更新 {self.stats['updated']}/{len(apps)} 条"
        )
        for grade in ['A', 'B', 'C', 'D', 'F']:
            count = self.stats['grade_distribution'].get(grade, 0)
            if count:
                logger.info(f"  {grade}级 (>={self.GRADE_THRESHOLDS[grade]:.0%}): {count} 条")

    def _calculate_score(self, app: dict, multi_source_pkgs: set) -> float:
        """计算单条记录的质量分"""
        score = 0.0

        # has_package_name
        if self._has_value(app.get('package_name')):
            score += self.weights.get('has_package_name', 0)

        # has_app_name
        if self._has_value(app.get('app_name')):
            score += self.weights.get('has_app_name', 0)

        # has_enterprise_name
        if self._has_value(app.get('enterprise_name')):
            score += self.weights.get('has_enterprise_name', 0)

        # has_version
        if self._has_value(app.get('version')):
            score += self.weights.get('has_version', 0)

        # has_developer
        if self._has_value(app.get('developer')):
            score += self.weights.get('has_developer', 0)

        # has_description
        if self._has_value(app.get('description')):
            score += self.weights.get('has_description', 0)

        # has_download_count
        if self._has_value(app.get('download_count')):
            score += self.weights.get('has_download_count', 0)

        # multi_source_verified
        pkg = app.get('package_name', '')
        if pkg in multi_source_pkgs:
            score += self.weights.get('multi_source_verified', 0)

        return min(score, 1.0)

    def _get_multi_source_packages(self, apps: list[dict]) -> set:
        """找出在多个来源出现的包名"""
        pkg_sources = defaultdict(set)
        for app in apps:
            pkg = app.get('package_name', '')
            source = app.get('source_site', '')
            if pkg and source:
                pkg_sources[pkg].add(source)

        return {pkg for pkg, sources in pkg_sources.items() if len(sources) >= 2}

    @staticmethod
    def _has_value(value) -> bool:
        """判断字段是否有有效值"""
        if value is None:
            return False
        if isinstance(value, str):
            return len(value.strip()) > 0
        return bool(value)

    def _get_grade(self, score: float) -> str:
        """将评分转换为等级"""
        for grade in ['A', 'B', 'C', 'D']:
            if score >= self.GRADE_THRESHOLDS[grade]:
                return grade
        return 'F'

    def get_summary(self) -> dict:
        """返回评分汇总信息"""
        return {
            'total_records': self.stats['total'],
            'average_score': round(self.stats['avg_score'], 4),
            'grade_distribution': dict(self.stats['grade_distribution']),
            'updated': self.stats['updated'],
        }
