"""
数据清洗模块
规范化字段格式、修正常见脏数据
"""
import logging
import re
import unicodedata
from typing import Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.db import AppInfoDB

logger = logging.getLogger('crawler.pipeline.cleaner')


class DataCleaner:
    """
    数据清洗处理器

    处理内容：
    1. 文本规范化：全角→半角、去除控制字符、标准化空白
    2. 包名清洗：统一小写、校验格式
    3. 应用名清洗：去除多余修饰词、标准化名称
    4. 版本号规范化
    5. 下载量格式统一
    6. 开发者名称清洗
    7. URL规范化
    """

    def __init__(self, db: AppInfoDB):
        self.db = db
        self.stats = {
            'total': 0,
            'cleaned': 0,
        }

    def run(self):
        """执行数据清洗"""
        apps = self.db.get_all_apps()
        self.stats['total'] = len(apps)
        logger.info(f"数据清洗开始，共 {len(apps)} 条记录")

        cleaned_count = 0
        conn = self.db._get_conn()

        for app in apps:
            updates = {}

            # 1. 包名清洗
            pkg = self._clean_package_name(app.get('package_name', ''))
            if pkg != app.get('package_name', ''):
                updates['package_name'] = pkg

            # 2. 应用名清洗
            name = self._clean_app_name(app.get('app_name', ''))
            if name != app.get('app_name', ''):
                updates['app_name'] = name

            # 3. 版本号规范化
            ver = self._clean_version(app.get('version', ''))
            if ver != app.get('version', ''):
                updates['version'] = ver

            # 4. 下载量格式统一
            dl = self._clean_download_count(app.get('download_count', ''))
            if dl != app.get('download_count', ''):
                updates['download_count'] = dl

            # 5. 开发者清洗
            dev = self._clean_developer(app.get('developer', ''))
            if dev != app.get('developer', ''):
                updates['developer'] = dev

            # 6. 企业名清洗
            ent = self._clean_enterprise_name(app.get('enterprise_name', ''))
            if ent != app.get('enterprise_name', ''):
                updates['enterprise_name'] = ent

            # 7. 描述清洗
            desc = self._clean_description(app.get('description', ''))
            if desc != app.get('description', ''):
                updates['description'] = desc

            # 8. URL规范化
            url = self._clean_url(app.get('source_url', ''))
            if url != app.get('source_url', ''):
                updates['source_url'] = url

            # 有更新则写入
            if updates:
                set_clause = ', '.join(f'{k} = ?' for k in updates.keys())
                try:
                    conn.execute(
                        f'UPDATE app_info SET {set_clause} WHERE id = ?',
                        (*updates.values(), app['id'])
                    )
                    cleaned_count += 1
                except Exception as e:
                    logger.debug(f"清洗记录 {app['id']} 失败: {e}")

        conn.commit()
        self.stats['cleaned'] = cleaned_count
        logger.info(f"数据清洗完成，{cleaned_count}/{len(apps)} 条记录被更新")

    # ----------------------------------------------------------
    # 文本规范化工具
    # ----------------------------------------------------------

    @staticmethod
    def _normalize_text(text: str) -> str:
        """通用文本规范化：全角→半角、去控制字符、标准化空白"""
        if not text:
            return ''
        # NFKC规范化（全角→半角等）
        text = unicodedata.normalize('NFKC', text)
        # 去除控制字符（保留换行和Tab）
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        # 标准化空白：多个空格合并为一个
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    # ----------------------------------------------------------
    # 字段级清洗
    # ----------------------------------------------------------

    def _clean_package_name(self, pkg: str) -> str:
        """包名清洗：统一小写、去除多余字符"""
        if not pkg:
            return ''
        pkg = pkg.strip().lower()
        # 去掉可能的前缀（某些站点会带 "包名："）
        pkg = re.sub(r'^(包名[：:]\s*|package[：:]\s*)', '', pkg, flags=re.IGNORECASE)
        # 只保留合法包名字符
        pkg = re.sub(r'[^a-z0-9._]', '', pkg)
        # 去掉首尾的点号
        pkg = pkg.strip('.')
        return pkg

    def _clean_app_name(self, name: str) -> str:
        """应用名清洗"""
        if not name:
            return ''
        name = self._normalize_text(name)
        # 去除常见修饰后缀
        suffixes_to_remove = [
            r'\s*-\s*官方版$',
            r'\s*-\s*最新版$',
            r'\s*\(官方版\)$',
            r'\s*\(最新版\)$',
            r'\s*官方正版$',
            r'\s*免费版$',
            r'\s*\d+\.\d+(\.\d+)*$',  # 尾部版本号
        ]
        for pattern in suffixes_to_remove:
            name = re.sub(pattern, '', name)
        return name.strip()

    def _clean_version(self, version: str) -> str:
        """版本号规范化"""
        if not version:
            return ''
        version = self._normalize_text(version)
        # 去掉前缀 v/V
        version = re.sub(r'^[vV]\s*', '', version)
        # 提取版本号
        m = re.search(r'(\d+(?:\.\d+)+)', version)
        if m:
            return m.group(1)
        # 如果纯数字也接受
        m = re.search(r'(\d+)', version)
        if m:
            return m.group(1)
        return version.strip()

    def _clean_download_count(self, count: str) -> str:
        """下载量格式统一"""
        if not count:
            return ''
        count = self._normalize_text(count)
        # 去掉"次下载"、"次"、"下载"等后缀
        count = re.sub(r'\s*(次下载|次|下载|Downloads?)', '', count, flags=re.IGNORECASE)
        # 统一中文单位
        count = count.replace('万+', '万').replace('亿+', '亿')
        # 去掉 "+" 号
        count = count.replace('+', '')
        return count.strip()

    def _clean_developer(self, dev: str) -> str:
        """开发者名称清洗"""
        if not dev:
            return ''
        dev = self._normalize_text(dev)
        # 去掉常见前缀
        dev = re.sub(r'^(开发者[：:]\s*|开发商[：:]\s*|by\s+)', '', dev, flags=re.IGNORECASE)
        return dev.strip()

    def _clean_enterprise_name(self, name: str) -> str:
        """企业名称清洗"""
        if not name:
            return ''
        name = self._normalize_text(name)
        # 统一括号格式
        name = name.replace('（', '(').replace('）', ')')
        # 去掉行政区划层级前的修饰
        name = re.sub(r'^(中国|国内)\s*', '', name)
        return name.strip()

    def _clean_description(self, desc: str) -> str:
        """描述清洗"""
        if not desc:
            return ''
        desc = self._normalize_text(desc)
        # 截断过长描述（保留前500字符）
        if len(desc) > 500:
            desc = desc[:500] + '...'
        return desc.strip()

    def _clean_url(self, url: str) -> str:
        """URL规范化"""
        if not url:
            return ''
        url = url.strip()
        # 去掉尾部的 # 和 ?
        url = re.sub(r'[#?]$', '', url)
        # 去掉尾部的多余斜线（根路径除外）
        if url.count('/') > 3:
            url = url.rstrip('/')
        return url
