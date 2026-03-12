"""
SQLite 数据库操作模块
管理客户名称库(customers.db)和应用包信息库(results.db)
"""
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CUSTOMERS_DB, RESULTS_DB


# ============================================================
# 表定义
# ============================================================

CREATE_CUSTOMERS_TABLE = '''
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enterprise_name TEXT NOT NULL,
    product_line TEXT NOT NULL,
    industry TEXT DEFAULT '',
    source TEXT NOT NULL,
    known_app_name TEXT DEFAULT '',
    discovery_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(enterprise_name, product_line)
)
'''

CREATE_CUSTOMERS_INDEX = '''
CREATE INDEX IF NOT EXISTS idx_customers_product ON customers(product_line)
'''

CREATE_APPINFO_TABLE = '''
CREATE TABLE IF NOT EXISTS app_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_name TEXT NOT NULL,
    app_name TEXT NOT NULL,
    product_line TEXT NOT NULL,
    enterprise_name TEXT DEFAULT '',
    developer TEXT DEFAULT '',
    version TEXT DEFAULT '',
    version_code TEXT DEFAULT '',
    update_date TEXT DEFAULT '',
    download_count TEXT DEFAULT '',
    description TEXT DEFAULT '',
    source_site TEXT NOT NULL,
    source_url TEXT NOT NULL,
    discovery_method TEXT DEFAULT '',
    quality_score REAL DEFAULT 0,
    crawl_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(package_name, source_site)
)
'''

CREATE_APPINFO_INDEXES = [
    'CREATE INDEX IF NOT EXISTS idx_appinfo_package ON app_info(package_name)',
    'CREATE INDEX IF NOT EXISTS idx_appinfo_product ON app_info(product_line)',
    'CREATE INDEX IF NOT EXISTS idx_appinfo_enterprise ON app_info(enterprise_name)',
]


class Database:
    """线程安全的SQLite数据库操作类"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, timeout=30)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute('PRAGMA journal_mode=WAL')
            self._local.conn.execute('PRAGMA foreign_keys=ON')
        return self._local.conn

    @contextmanager
    def transaction(self):
        """事务上下文管理器"""
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_db(self):
        """初始化数据库表"""
        raise NotImplementedError

    def close(self):
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


class CustomerDB(Database):
    """企业客户名称库"""

    def __init__(self, db_path: str = CUSTOMERS_DB):
        super().__init__(db_path)

    def _init_db(self):
        conn = self._get_conn()
        conn.execute(CREATE_CUSTOMERS_TABLE)
        conn.execute(CREATE_CUSTOMERS_INDEX)
        conn.commit()

    def insert_customer(self, enterprise_name: str, product_line: str,
                        source: str, industry: str = '',
                        known_app_name: str = '') -> bool:
        """
        插入客户记录，存在则跳过。
        返回 True 表示新插入，False 表示已存在。
        """
        try:
            with self.transaction() as conn:
                before = conn.total_changes
                conn.execute(
                    '''INSERT OR IGNORE INTO customers
                       (enterprise_name, product_line, industry, source, known_app_name)
                       VALUES (?, ?, ?, ?, ?)''',
                    (enterprise_name, product_line, industry, source, known_app_name)
                )
                return conn.total_changes > before
        except sqlite3.Error:
            return False

    def batch_insert_customers(self, records: list[dict]) -> int:
        """
        批量插入客户记录。返回新插入条数。
        records: [{'enterprise_name', 'product_line', 'source', 'industry', 'known_app_name'}]
        """
        inserted = 0
        with self.transaction() as conn:
            for r in records:
                try:
                    before = conn.total_changes
                    conn.execute(
                        '''INSERT OR IGNORE INTO customers
                           (enterprise_name, product_line, industry, source, known_app_name)
                           VALUES (?, ?, ?, ?, ?)''',
                        (r['enterprise_name'], r['product_line'],
                         r.get('industry', ''), r['source'],
                         r.get('known_app_name', ''))
                    )
                    if conn.total_changes > before:
                        inserted += 1
                except sqlite3.Error:
                    continue
        return inserted

    def get_all_customers(self, product_line: Optional[str] = None) -> list[dict]:
        """获取所有客户记录"""
        conn = self._get_conn()
        if product_line:
            rows = conn.execute(
                'SELECT * FROM customers WHERE product_line = ? ORDER BY id',
                (product_line,)
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM customers ORDER BY id'
            ).fetchall()
        return [dict(row) for row in rows]

    def get_customer_names(self, product_line: Optional[str] = None) -> list[str]:
        """获取客户名称列表"""
        conn = self._get_conn()
        if product_line:
            rows = conn.execute(
                'SELECT DISTINCT enterprise_name FROM customers WHERE product_line = ?',
                (product_line,)
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT DISTINCT enterprise_name FROM customers'
            ).fetchall()
        return [row['enterprise_name'] for row in rows]

    def count(self) -> int:
        conn = self._get_conn()
        return conn.execute('SELECT COUNT(*) FROM customers').fetchone()[0]


class AppInfoDB(Database):
    """应用包信息库"""

    def __init__(self, db_path: str = RESULTS_DB):
        super().__init__(db_path)

    def _init_db(self):
        conn = self._get_conn()
        conn.execute(CREATE_APPINFO_TABLE)
        for idx_sql in CREATE_APPINFO_INDEXES:
            conn.execute(idx_sql)
        conn.commit()

    def insert_app(self, **kwargs) -> bool:
        """
        插入应用记录，存在则跳过。
        必须参数: package_name, app_name, product_line, source_site, source_url
        """
        required = ['package_name', 'app_name', 'product_line', 'source_site', 'source_url']
        for key in required:
            if key not in kwargs:
                raise ValueError(f"缺少必须字段: {key}")

        fields = [
            'package_name', 'app_name', 'product_line', 'enterprise_name',
            'developer', 'version', 'version_code', 'update_date',
            'download_count', 'description', 'source_site', 'source_url',
            'discovery_method', 'quality_score',
        ]
        values = {f: kwargs.get(f, '') for f in fields}
        values['quality_score'] = kwargs.get('quality_score', 0.0)

        placeholders = ', '.join(['?'] * len(values))
        columns = ', '.join(values.keys())

        try:
            with self.transaction() as conn:
                before = conn.total_changes
                conn.execute(
                    f'INSERT OR IGNORE INTO app_info ({columns}) VALUES ({placeholders})',
                    tuple(values.values())
                )
                return conn.total_changes > before
        except sqlite3.Error:
            return False

    def batch_insert_apps(self, records: list[dict]) -> int:
        """批量插入应用记录。返回新插入条数。"""
        inserted = 0
        with self.transaction() as conn:
            for r in records:
                try:
                    fields = [
                        'package_name', 'app_name', 'product_line', 'enterprise_name',
                        'developer', 'version', 'version_code', 'update_date',
                        'download_count', 'description', 'source_site', 'source_url',
                        'discovery_method', 'quality_score',
                    ]
                    values = {f: r.get(f, '') for f in fields}
                    values['quality_score'] = r.get('quality_score', 0.0)
                    placeholders = ', '.join(['?'] * len(values))
                    columns = ', '.join(values.keys())
                    before = conn.total_changes
                    conn.execute(
                        f'INSERT OR IGNORE INTO app_info ({columns}) VALUES ({placeholders})',
                        tuple(values.values())
                    )
                    if conn.total_changes > before:
                        inserted += 1
                except sqlite3.Error:
                    continue
        return inserted

    def update_app(self, package_name: str, source_site: str, **kwargs) -> bool:
        """更新已有应用记录的字段"""
        if not kwargs:
            return False
        set_clause = ', '.join([f'{k} = ?' for k in kwargs.keys()])
        try:
            with self.transaction() as conn:
                before = conn.total_changes
                conn.execute(
                    f'UPDATE app_info SET {set_clause} WHERE package_name = ? AND source_site = ?',
                    (*kwargs.values(), package_name, source_site)
                )
                return conn.total_changes > before
        except sqlite3.Error:
            return False

    def get_all_apps(self, product_line: Optional[str] = None) -> list[dict]:
        """获取所有应用记录"""
        conn = self._get_conn()
        if product_line:
            rows = conn.execute(
                'SELECT * FROM app_info WHERE product_line = ? ORDER BY id',
                (product_line,)
            ).fetchall()
        else:
            rows = conn.execute('SELECT * FROM app_info ORDER BY id').fetchall()
        return [dict(row) for row in rows]

    def get_package_names(self) -> set[str]:
        """获取所有已知包名集合"""
        conn = self._get_conn()
        rows = conn.execute('SELECT DISTINCT package_name FROM app_info').fetchall()
        return {row['package_name'] for row in rows}

    def search_apps(self, keyword: str) -> list[dict]:
        """按关键词搜索应用（包名或应用名）"""
        conn = self._get_conn()
        rows = conn.execute(
            '''SELECT * FROM app_info
               WHERE package_name LIKE ? OR app_name LIKE ?
               ORDER BY quality_score DESC''',
            (f'%{keyword}%', f'%{keyword}%')
        ).fetchall()
        return [dict(row) for row in rows]

    def count(self) -> int:
        conn = self._get_conn()
        return conn.execute('SELECT COUNT(*) FROM app_info').fetchone()[0]

    def get_stats(self) -> dict:
        """获取统计信息"""
        conn = self._get_conn()
        total = conn.execute('SELECT COUNT(*) FROM app_info').fetchone()[0]
        by_product = {}
        for row in conn.execute(
            'SELECT product_line, COUNT(*) as cnt FROM app_info GROUP BY product_line'
        ).fetchall():
            by_product[row['product_line']] = row['cnt']
        by_method = {}
        for row in conn.execute(
            'SELECT discovery_method, COUNT(*) as cnt FROM app_info GROUP BY discovery_method'
        ).fetchall():
            by_method[row['discovery_method']] = row['cnt']
        return {
            'total': total,
            'by_product_line': by_product,
            'by_discovery_method': by_method,
        }
