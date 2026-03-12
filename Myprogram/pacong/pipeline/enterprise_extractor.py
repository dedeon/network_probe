"""
企业名称智能提取模块
从应用名、开发者名称、描述等字段中提取企业名称
"""
import logging
import re
from typing import Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.db import AppInfoDB
from config import PRODUCT_LINES

logger = logging.getLogger('crawler.pipeline.enterprise_extractor')

# 企业名称后缀（用于正则匹配）
ENTERPRISE_SUFFIXES = [
    r'(?:股份)?有限公司',
    r'有限责任公司',
    r'集团(?:有限公司)?',
    r'(?:总|分)?公司',
    r'控股',
    r'科技',
    r'技术',
    r'网络',
    r'信息',
    r'软件',
    r'数据',
    r'传媒',
    r'文化',
]

# 企业名称前缀（地名等）
ENTERPRISE_PREFIXES = [
    r'(?:北京|上海|广州|深圳|杭州|成都|武汉|南京|西安|重庆)',
    r'(?:天津|苏州|长沙|郑州|青岛|大连|宁波|厦门|无锡|合肥)',
    r'(?:福州|济南|沈阳|哈尔滨|昆明|贵阳|南宁|太原|南昌|兰州)',
    r'(?:海口|银川|西宁|呼和浩特|拉萨|乌鲁木齐)',
    r'(?:浙江|江苏|广东|山东|河南|四川|湖北|湖南|福建|安徽)',
    r'(?:河北|陕西|云南|贵州|广西|海南|甘肃|青海|内蒙古|宁夏|西藏|新疆|吉林|辽宁|黑龙江|山西|江西)',
    r'(?:中国|中华)',
]

# 组合企业名称正则模式
_prefix_pattern = '|'.join(ENTERPRISE_PREFIXES)
_suffix_pattern = '|'.join(ENTERPRISE_SUFFIXES)

# 完整企业名称模式
ENTERPRISE_PATTERN = re.compile(
    rf'(?:{_prefix_pattern})?'
    r'[\u4e00-\u9fff\w]+'
    rf'(?:{_suffix_pattern})',
    re.UNICODE
)

# 简称提取模式（从应用名中推断）
APP_NAME_ENTERPRISE_PATTERNS = [
    # "XX企业微信" → "XX"
    re.compile(r'^(.{2,10}?)(?:企业微信|企微|钉钉|飞书|移动办公|OA)', re.UNICODE),
    # "企业微信-XX版" → "XX"
    re.compile(r'(?:企业微信|企微|钉钉|飞书)[·\-\s]*(.{2,15}?)(?:版|端|$)', re.UNICODE),
    # "XX办公" or "XX政务"
    re.compile(r'^(.{2,8}?)(?:政务|办公|协同|移动)', re.UNICODE),
]

# 需要排除的虚假企业名
EXCLUDE_NAMES = {
    '腾讯', '阿里巴巴', '字节跳动',  # 平台方本身
    '腾讯科技', '阿里巴巴集团', '字节跳动有限公司',
    '深圳市腾讯计算机系统有限公司', '阿里巴巴(中国)有限公司',
    '北京飞书科技有限公司', '钉钉(中国)信息技术有限公司',
    '安卓', 'Android', 'Google', '华为', '小米', 'OPPO', 'vivo',
    '应用宝', '豌豆荚',
    '最新版', '官方版', '手机版', '安卓版',  # 版本修饰
    '教育', '教育版', '政务', '政务版', '企业版', '专属版',  # 功能修饰
    '定制版', '国际版', '海外版', '青春版',
    '测试', '测试版', '内测版', '体验版',  # 测试词
}

# 政务类简称→全称映射
GOV_NAME_MAP = {
    '浙政钉': '浙江省人民政府',
    '粤政易': '广东省人民政府',
    '赣政通': '江西省人民政府',
    '鄂汇办': '湖北省人民政府',
    '苏政通': '江苏省人民政府',
    '豫政通': '河南省人民政府',
    '鲁政通': '山东省人民政府',
    '闽政通': '福建省人民政府',
    '皖政通': '安徽省人民政府',
    '政务钉钉': '政务机构(通用)',
    '政务微信': '政务机构(通用)',
}


class EnterpriseExtractor:
    """
    企业名称智能提取处理器

    提取优先级：
    1. 已有 enterprise_name → 直接使用
    2. 开发者名称 → 尝试提取企业名
    3. 应用名称 → 通过模式匹配提取
    4. 描述文本 → 通过NLP提取
    5. 政务类应用 → 映射到政府机构
    """

    def __init__(self, db: AppInfoDB):
        self.db = db
        self.stats = {
            'total': 0,
            'already_has': 0,
            'from_developer': 0,
            'from_app_name': 0,
            'from_description': 0,
            'from_gov_map': 0,
            'not_extracted': 0,
        }

    def run(self):
        """执行企业名称提取"""
        apps = self.db.get_all_apps()
        self.stats['total'] = len(apps)
        logger.info(f"企业名称提取开始，共 {len(apps)} 条记录")

        conn = self.db._get_conn()

        for app in apps:
            current = (app.get('enterprise_name') or '').strip()
            if current and current not in EXCLUDE_NAMES:
                self.stats['already_has'] += 1
                continue

            # 尝试多种提取方式
            enterprise = self._extract(app)

            if enterprise and enterprise not in EXCLUDE_NAMES:
                try:
                    conn.execute(
                        'UPDATE app_info SET enterprise_name = ? WHERE id = ?',
                        (enterprise, app['id'])
                    )
                except Exception as e:
                    logger.debug(f"更新企业名失败 (id={app['id']}): {e}")
            else:
                self.stats['not_extracted'] += 1

        conn.commit()

        logger.info(
            f"企业名称提取完成: "
            f"已有{self.stats['already_has']}, "
            f"开发者提取{self.stats['from_developer']}, "
            f"应用名提取{self.stats['from_app_name']}, "
            f"描述提取{self.stats['from_description']}, "
            f"政务映射{self.stats['from_gov_map']}, "
            f"未提取{self.stats['not_extracted']}"
        )

    def _extract(self, app: dict) -> Optional[str]:
        """按优先级尝试提取企业名称"""
        # 1. 从开发者名称提取
        enterprise = self._extract_from_developer(app.get('developer', ''))
        if enterprise:
            self.stats['from_developer'] += 1
            return enterprise

        # 2. 从应用名称提取
        enterprise = self._extract_from_app_name(
            app.get('app_name', ''), app.get('package_name', '')
        )
        if enterprise:
            self.stats['from_app_name'] += 1
            return enterprise

        # 3. 政务类映射
        enterprise = self._extract_from_gov_map(
            app.get('app_name', ''), app.get('package_name', '')
        )
        if enterprise:
            self.stats['from_gov_map'] += 1
            return enterprise

        # 4. 从描述中提取
        enterprise = self._extract_from_description(app.get('description', ''))
        if enterprise:
            self.stats['from_description'] += 1
            return enterprise

        return None

    def _extract_from_developer(self, developer: str) -> Optional[str]:
        """从开发者名称中提取企业名"""
        if not developer:
            return None
        developer = developer.strip()

        # 如果开发者名本身就像企业名（中文为主、长度合适），优先直接使用
        # 避免正则匹配截断（如"浙江省大数据中心"被截到"浙江省大数据"）
        if re.match(r'^[\u4e00-\u9fff]', developer) and 4 <= len(developer) <= 30:
            if developer not in EXCLUDE_NAMES:
                return developer

        # 否则尝试正则提取
        m = ENTERPRISE_PATTERN.search(developer)
        if m:
            name = m.group(0)
            if len(name) >= 4 and name not in EXCLUDE_NAMES:
                return name

        return None

    def _extract_from_app_name(self, app_name: str, package_name: str) -> Optional[str]:
        """从应用名称中推断企业名"""
        if not app_name:
            return None

        # 尝试多种模式
        for pattern in APP_NAME_ENTERPRISE_PATTERNS:
            m = pattern.search(app_name)
            if m:
                candidate = m.group(1).strip()
                # 过滤太短或无意义的匹配（至少3个字符）
                if len(candidate) >= 3 and candidate not in EXCLUDE_NAMES:
                    # 排除纯数字、纯字母等
                    if re.search(r'[\u4e00-\u9fff]', candidate):
                        return candidate

        # 从包名推断（如 com.xxx.wework.companyname）
        enterprise = self._extract_from_package_name(package_name)
        if enterprise:
            return enterprise

        return None

    def _extract_from_package_name(self, package_name: str) -> Optional[str]:
        """
        从包名推断企业信息。
        如 com.tencent.wework.abc → "abc" 可能是企业标识
        """
        if not package_name:
            return None

        # 已知基础包名
        base_packages = {
            'com.tencent.wework': '企业微信',
            'com.alibaba.android.rimet': '钉钉',
            'com.ss.android.lark': '飞书',
        }

        for base_pkg, product in base_packages.items():
            if package_name.startswith(base_pkg + '.') and package_name != base_pkg:
                suffix = package_name[len(base_pkg) + 1:]
                # 排除常见非企业后缀
                non_enterprise = {
                    'debug', 'test', 'dev', 'staging', 'beta',
                    'hd', 'lite', 'pro', 'tablet', 'pad',
                    'gov', 'custom', 'channel',
                }
                parts = suffix.split('.')
                if parts[0].lower() not in non_enterprise and len(parts[0]) >= 3:
                    # 这是个企业标识，但无法直接转化为中文企业名
                    # 仅作为参考标记
                    return None

        return None

    def _extract_from_gov_map(self, app_name: str, package_name: str) -> Optional[str]:
        """从政务类映射中匹配"""
        if not app_name:
            return None

        for keyword, gov_name in GOV_NAME_MAP.items():
            if keyword in app_name:
                return gov_name

        # 通用政务应用检测
        if re.search(r'政务|政府|gov', app_name + package_name, re.IGNORECASE):
            return '政务机构(通用)'

        return None

    def _extract_from_description(self, description: str) -> Optional[str]:
        """从描述文本中提取企业名"""
        if not description or len(description) < 10:
            return None

        # 查找完整企业名称
        matches = ENTERPRISE_PATTERN.findall(description)
        if matches:
            # 过滤并返回最可能的企业名
            # 去除前导非企业名词（如"由"、"是"、"为"等）
            non_name_prefixes = re.compile(r'^[由是为在从和与及或的了]')
            for name in matches:
                name = non_name_prefixes.sub('', name)
                if len(name) >= 4 and name not in EXCLUDE_NAMES:
                    return name

        # 尝试提取 "由XX开发/提供/运营" 模式
        patterns = [
            re.compile(r'由\s*([\u4e00-\u9fff\w]{2,20})\s*(?:开发|提供|运营|推出)', re.UNICODE),
            re.compile(r'([\u4e00-\u9fff\w]{2,20})\s*(?:出品|研发|打造)', re.UNICODE),
            re.compile(r'(?:开发者|开发商|公司)[：:]\s*([\u4e00-\u9fff\w]{2,20})', re.UNICODE),
        ]

        for p in patterns:
            m = p.search(description)
            if m:
                candidate = m.group(1).strip()
                if len(candidate) >= 4 and candidate not in EXCLUDE_NAMES:
                    return candidate

        return None
