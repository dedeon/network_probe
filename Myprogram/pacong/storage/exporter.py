"""
数据导出模块 - 支持CSV、JSON、Excel格式
功能：
- 客户库导出（CSV/JSON）
- 应用包信息导出（CSV/JSON）
- 按产品线分别导出
- 按质量等级过滤导出
- 统计报告生成
- Excel多Sheet导出
"""
import csv
import json
import logging
import os
from datetime import datetime
from typing import Optional

import pandas as pd

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    CUSTOMERS_CSV, RESULTS_CSV, RESULTS_JSON, OUTPUT_DIR
)
from storage.db import CustomerDB, AppInfoDB

logger = logging.getLogger('crawler.exporter')

# 导出文件路径常量
CUSTOMERS_JSON = os.path.join(OUTPUT_DIR, 'customers.json')
REPORT_JSON = os.path.join(OUTPUT_DIR, 'report.json')
REPORT_TXT = os.path.join(OUTPUT_DIR, 'report.txt')
EXCEL_FILE = os.path.join(OUTPUT_DIR, 'results.xlsx')

# 列名中英映射
APP_COLUMNS_CN = {
    'id': 'ID',
    'package_name': '包名',
    'app_name': '应用名称',
    'product_line': '产品线',
    'enterprise_name': '企业名称',
    'developer': '开发者',
    'version': '版本号',
    'version_code': '版本代码',
    'update_date': '更新日期',
    'download_count': '下载量',
    'description': '描述',
    'source_site': '来源站点',
    'source_url': '来源URL',
    'discovery_method': '发现方式',
    'quality_score': '质量评分',
    'crawl_time': '爬取时间',
}

CUSTOMER_COLUMNS_CN = {
    'id': 'ID',
    'enterprise_name': '企业名称',
    'product_line': '产品线',
    'industry': '行业',
    'source': '来源',
    'known_app_name': '已知应用名',
    'discovery_time': '发现时间',
}

# 质量等级映射
GRADE_THRESHOLDS = [
    (0.8, 'A'),
    (0.6, 'B'),
    (0.4, 'C'),
    (0.2, 'D'),
    (0.0, 'F'),
]


def _get_grade(score: float) -> str:
    """根据评分返回等级"""
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return 'F'


def _ensure_dir(filepath: str):
    """确保文件所在目录存在"""
    dirpath = os.path.dirname(filepath)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)


class DataExporter:
    """数据导出器"""

    def __init__(self, customer_db: Optional[CustomerDB] = None,
                 appinfo_db: Optional[AppInfoDB] = None):
        self.customer_db = customer_db or CustomerDB()
        self.appinfo_db = appinfo_db or AppInfoDB()

    # ============================================================
    # 客户库导出
    # ============================================================

    def export_customers_csv(self, filepath: str = CUSTOMERS_CSV,
                             product_line: Optional[str] = None,
                             use_cn_header: bool = True) -> str:
        """
        导出客户名称库为CSV
        Args:
            filepath: 输出文件路径
            product_line: 按产品线筛选（None表示全部）
            use_cn_header: 是否使用中文列头
        """
        records = self.customer_db.get_all_customers(product_line)
        if not records:
            logger.warning("客户库为空，无数据可导出")
            return filepath

        _ensure_dir(filepath)
        df = pd.DataFrame(records)

        if use_cn_header:
            df.rename(columns=CUSTOMER_COLUMNS_CN, inplace=True)

        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        logger.info(f"已导出 {len(records)} 条客户记录到 {filepath}")
        return filepath

    def export_customers_json(self, filepath: str = CUSTOMERS_JSON,
                              product_line: Optional[str] = None) -> str:
        """导出客户名称库为JSON"""
        records = self.customer_db.get_all_customers(product_line)
        if not records:
            logger.warning("客户库为空，无数据可导出")
            return filepath

        _ensure_dir(filepath)
        export_data = {
            'export_time': datetime.now().isoformat(),
            'total': len(records),
            'filter': {'product_line': product_line} if product_line else None,
            'data': records,
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"已导出 {len(records)} 条客户记录到 {filepath}")
        return filepath

    # ============================================================
    # 应用包信息导出
    # ============================================================

    def export_results_csv(self, filepath: str = RESULTS_CSV,
                           product_line: Optional[str] = None,
                           min_grade: Optional[str] = None,
                           use_cn_header: bool = True) -> str:
        """
        导出应用包信息为CSV
        Args:
            filepath: 输出文件路径
            product_line: 按产品线筛选
            min_grade: 最低质量等级（A/B/C/D/F），过滤低于此等级的记录
            use_cn_header: 是否使用中文列头
        """
        records = self._get_filtered_apps(product_line, min_grade)
        if not records:
            logger.warning("应用包信息库为空或筛选无结果，无数据可导出")
            return filepath

        _ensure_dir(filepath)
        df = pd.DataFrame(records)
        # 按质量评分降序排列
        if 'quality_score' in df.columns:
            df.sort_values('quality_score', ascending=False, inplace=True)

        if use_cn_header:
            df.rename(columns=APP_COLUMNS_CN, inplace=True)

        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        logger.info(f"已导出 {len(records)} 条应用记录到 {filepath}")
        return filepath

    def export_results_json(self, filepath: str = RESULTS_JSON,
                            product_line: Optional[str] = None,
                            min_grade: Optional[str] = None) -> str:
        """导出应用包信息为JSON"""
        records = self._get_filtered_apps(product_line, min_grade)
        if not records:
            logger.warning("应用包信息库为空或筛选无结果，无数据可导出")
            return filepath

        # 按质量评分降序排列
        records.sort(key=lambda x: x.get('quality_score', 0), reverse=True)

        _ensure_dir(filepath)
        export_data = {
            'export_time': datetime.now().isoformat(),
            'total': len(records),
            'filter': {
                'product_line': product_line,
                'min_grade': min_grade,
            } if product_line or min_grade else None,
            'data': records,
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"已导出 {len(records)} 条应用记录到 {filepath}")
        return filepath

    # ============================================================
    # Excel多Sheet导出
    # ============================================================

    def export_excel(self, filepath: str = EXCEL_FILE) -> str:
        """
        导出为Excel文件（多Sheet）
        - Sheet "全部应用": 所有应用记录
        - Sheet "企业微信"/"钉钉"/"飞书": 按产品线分Sheet
        - Sheet "客户名录": 客户记录
        - Sheet "统计概要": 汇总统计
        """
        _ensure_dir(filepath)

        all_apps = self.appinfo_db.get_all_apps()
        all_customers = self.customer_db.get_all_customers()

        try:
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Sheet 1: 全部应用
                if all_apps:
                    df_all = pd.DataFrame(all_apps)
                    df_all.sort_values('quality_score', ascending=False, inplace=True)
                    df_all.rename(columns=APP_COLUMNS_CN, inplace=True)
                    df_all.to_excel(writer, sheet_name='全部应用', index=False)

                    # 按产品线分Sheet
                    df_raw = pd.DataFrame(all_apps)
                    for pl in df_raw['product_line'].unique():
                        if not pl:
                            continue
                        df_pl = df_raw[df_raw['product_line'] == pl].copy()
                        df_pl.sort_values('quality_score', ascending=False, inplace=True)
                        df_pl.rename(columns=APP_COLUMNS_CN, inplace=True)
                        sheet_name = pl[:31]  # Excel sheet名最长31字符
                        df_pl.to_excel(writer, sheet_name=sheet_name, index=False)

                # Sheet: 客户名录
                if all_customers:
                    df_cust = pd.DataFrame(all_customers)
                    df_cust.rename(columns=CUSTOMER_COLUMNS_CN, inplace=True)
                    df_cust.to_excel(writer, sheet_name='客户名录', index=False)

                # Sheet: 统计概要
                stats = self._build_stats(all_apps, all_customers)
                stats_rows = self._stats_to_rows(stats)
                df_stats = pd.DataFrame(stats_rows, columns=['指标', '值'])
                df_stats.to_excel(writer, sheet_name='统计概要', index=False)

            logger.info(f"已导出Excel文件到 {filepath}")
        except ImportError:
            logger.warning("openpyxl未安装，跳过Excel导出。可执行: pip install openpyxl")
        except Exception as e:
            logger.error(f"Excel导出失败: {e}")

        return filepath

    # ============================================================
    # 按产品线分别导出
    # ============================================================

    def export_by_product_line(self, fmt: str = 'csv') -> dict:
        """
        按产品线分别导出文件
        Args:
            fmt: 'csv' 或 'json'
        Returns:
            {产品线: 文件路径} 映射
        """
        all_apps = self.appinfo_db.get_all_apps()
        if not all_apps:
            logger.warning("应用包信息库为空")
            return {}

        # 收集所有产品线
        product_lines = set()
        for app in all_apps:
            pl = app.get('product_line', '')
            if pl:
                product_lines.add(pl)

        result = {}
        for pl in sorted(product_lines):
            safe_name = pl.replace('/', '_').replace('\\', '_')
            if fmt == 'json':
                fpath = os.path.join(OUTPUT_DIR, f'results_{safe_name}.json')
                self.export_results_json(fpath, product_line=pl)
            else:
                fpath = os.path.join(OUTPUT_DIR, f'results_{safe_name}.csv')
                self.export_results_csv(fpath, product_line=pl)
            result[pl] = fpath

        logger.info(f"已按产品线导出 {len(result)} 个文件")
        return result

    # ============================================================
    # 统计报告
    # ============================================================

    def export_report(self, json_path: str = REPORT_JSON,
                      txt_path: str = REPORT_TXT) -> dict:
        """
        生成并导出统计报告
        Returns:
            统计数据字典
        """
        all_apps = self.appinfo_db.get_all_apps()
        all_customers = self.customer_db.get_all_customers()
        stats = self._build_stats(all_apps, all_customers)

        # 导出JSON报告
        _ensure_dir(json_path)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"统计报告(JSON)已导出到 {json_path}")

        # 导出文本报告
        _ensure_dir(txt_path)
        txt = self._format_report_txt(stats)
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(txt)
        logger.info(f"统计报告(TXT)已导出到 {txt_path}")

        return stats

    # ============================================================
    # 批量导出
    # ============================================================

    def export_all(self) -> dict:
        """导出所有数据（CSV + JSON + 报告）"""
        result = {}
        result['customers_csv'] = self.export_customers_csv()
        result['customers_json'] = self.export_customers_json()
        result['results_csv'] = self.export_results_csv()
        result['results_json'] = self.export_results_json()

        # Excel导出（若openpyxl可用）
        try:
            result['results_excel'] = self.export_excel()
        except Exception as e:
            logger.warning(f"Excel导出跳过: {e}")

        # 按产品线分文件
        by_pl = self.export_by_product_line('csv')
        for pl, path in by_pl.items():
            result[f'results_{pl}_csv'] = path

        # 统计报告
        self.export_report()
        result['report_json'] = REPORT_JSON
        result['report_txt'] = REPORT_TXT

        return result

    def print_summary(self):
        """打印数据汇总到控制台"""
        all_apps = self.appinfo_db.get_all_apps()
        all_customers = self.customer_db.get_all_customers()
        stats = self._build_stats(all_apps, all_customers)
        txt = self._format_report_txt(stats)
        print(txt)

    # ============================================================
    # 内部方法
    # ============================================================

    def _get_filtered_apps(self, product_line: Optional[str] = None,
                           min_grade: Optional[str] = None) -> list[dict]:
        """获取经过筛选的应用记录"""
        records = self.appinfo_db.get_all_apps(product_line)

        if min_grade and records:
            grade_order = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'F': 4}
            min_rank = grade_order.get(min_grade.upper(), 4)
            records = [
                r for r in records
                if grade_order.get(_get_grade(r.get('quality_score', 0)), 4) <= min_rank
            ]
        return records

    def _build_stats(self, all_apps: list[dict],
                     all_customers: list[dict]) -> dict:
        """构建统计数据"""
        now = datetime.now().isoformat()

        # 基础计数
        total_apps = len(all_apps)
        total_customers = len(all_customers)

        # 按产品线分组
        by_product = {}
        for app in all_apps:
            pl = app.get('product_line', '未分类')
            by_product.setdefault(pl, 0)
            by_product[pl] += 1

        # 按来源站点分组
        by_source = {}
        for app in all_apps:
            src = app.get('source_site', '未知')
            by_source.setdefault(src, 0)
            by_source[src] += 1

        # 按发现方式分组
        by_method = {}
        for app in all_apps:
            m = app.get('discovery_method', '未知') or '未知'
            by_method.setdefault(m, 0)
            by_method[m] += 1

        # 质量评分分布
        grade_dist = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        scores = []
        for app in all_apps:
            score = app.get('quality_score', 0)
            scores.append(score)
            grade_dist[_get_grade(score)] += 1

        avg_score = sum(scores) / len(scores) if scores else 0
        max_score = max(scores) if scores else 0
        min_score = min(scores) if scores else 0

        # 企业名提取率
        with_enterprise = sum(1 for a in all_apps if a.get('enterprise_name'))
        enterprise_rate = (with_enterprise / total_apps * 100) if total_apps else 0

        # 唯一包名数
        unique_packages = len(set(a['package_name'] for a in all_apps))

        # 客户按产品线
        cust_by_product = {}
        for c in all_customers:
            pl = c.get('product_line', '未分类')
            cust_by_product.setdefault(pl, 0)
            cust_by_product[pl] += 1

        return {
            'report_time': now,
            'summary': {
                'total_apps': total_apps,
                'unique_packages': unique_packages,
                'total_customers': total_customers,
                'enterprise_extraction_rate': round(enterprise_rate, 1),
            },
            'by_product_line': by_product,
            'by_source_site': by_source,
            'by_discovery_method': by_method,
            'quality': {
                'average_score': round(avg_score, 4),
                'max_score': round(max_score, 4),
                'min_score': round(min_score, 4),
                'grade_distribution': grade_dist,
            },
            'customers_by_product_line': cust_by_product,
        }

    def _stats_to_rows(self, stats: dict) -> list[list]:
        """将统计数据转换为行列表（用于Excel Sheet）"""
        rows = []
        s = stats.get('summary', {})
        rows.append(['应用记录总数', s.get('total_apps', 0)])
        rows.append(['唯一包名数', s.get('unique_packages', 0)])
        rows.append(['客户总数', s.get('total_customers', 0)])
        rows.append(['企业名提取率', f"{s.get('enterprise_extraction_rate', 0)}%"])
        rows.append(['', ''])

        q = stats.get('quality', {})
        rows.append(['平均质量评分', q.get('average_score', 0)])
        rows.append(['最高评分', q.get('max_score', 0)])
        rows.append(['最低评分', q.get('min_score', 0)])
        rows.append(['', ''])

        rows.append(['质量等级分布', ''])
        for grade, count in q.get('grade_distribution', {}).items():
            rows.append([f'  等级 {grade}', count])
        rows.append(['', ''])

        rows.append(['按产品线', ''])
        for pl, count in stats.get('by_product_line', {}).items():
            rows.append([f'  {pl}', count])
        rows.append(['', ''])

        rows.append(['按来源站点', ''])
        for src, count in stats.get('by_source_site', {}).items():
            rows.append([f'  {src}', count])

        return rows

    def _format_report_txt(self, stats: dict) -> str:
        """格式化文本报告"""
        s = stats.get('summary', {})
        q = stats.get('quality', {})
        lines = [
            '',
            '=' * 60,
            '  爬取结果统计报告',
            f'  生成时间: {stats.get("report_time", "")}',
            '=' * 60,
            '',
            '  【基础统计】',
            f'    应用记录总数:     {s.get("total_apps", 0)}',
            f'    唯一包名数:       {s.get("unique_packages", 0)}',
            f'    企业客户数量:     {s.get("total_customers", 0)}',
            f'    企业名提取率:     {s.get("enterprise_extraction_rate", 0)}%',
            '',
            '  【质量评分】',
            f'    平均分: {q.get("average_score", 0):.4f}',
            f'    最高分: {q.get("max_score", 0):.4f}',
            f'    最低分: {q.get("min_score", 0):.4f}',
            '',
            '    等级分布:',
        ]
        for grade, count in q.get('grade_distribution', {}).items():
            bar = '#' * min(count, 50)
            lines.append(f'      {grade}: {count:>4d}  {bar}')

        lines.append('')
        lines.append('  【按产品线】')
        for pl, count in stats.get('by_product_line', {}).items():
            lines.append(f'    {pl}: {count}')

        lines.append('')
        lines.append('  【按来源站点】')
        for src, count in stats.get('by_source_site', {}).items():
            lines.append(f'    {src}: {count}')

        lines.append('')
        lines.append('  【按发现方式】')
        for m, count in stats.get('by_discovery_method', {}).items():
            lines.append(f'    {m}: {count}')

        if stats.get('customers_by_product_line'):
            lines.append('')
            lines.append('  【客户按产品线】')
            for pl, count in stats['customers_by_product_line'].items():
                lines.append(f'    {pl}: {count}')

        lines.append('')
        lines.append('=' * 60)
        lines.append('')
        return '\n'.join(lines)
