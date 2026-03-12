"""
企业IM安卓客户端包信息爬虫 - 全局配置
"""
import os
import re

# ============================================================
# 项目路径配置
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
CUSTOMERS_DB = os.path.join(OUTPUT_DIR, 'customers.db')
RESULTS_DB = os.path.join(OUTPUT_DIR, 'results.db')
CUSTOMERS_CSV = os.path.join(OUTPUT_DIR, 'customers.csv')
RESULTS_CSV = os.path.join(OUTPUT_DIR, 'results.csv')
RESULTS_JSON = os.path.join(OUTPUT_DIR, 'results.json')

# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# 目标产品线配置
# ============================================================
PRODUCT_LINES = {
    '企业微信': {
        'official_package': 'com.tencent.wework',
        'package_patterns': [
            re.compile(r'com\.tencent\.wework.*', re.IGNORECASE),
            re.compile(r'.*wework.*', re.IGNORECASE),
            re.compile(r'.*wecom.*', re.IGNORECASE),
        ],
        'name_keywords': ['企业微信', '企微', 'WeWork', 'WeCom', '政务微信'],
        'official_sites': [
            'https://work.weixin.qq.com',
            'https://wecom.work.weixin.qq.com',
        ],
    },
    '钉钉': {
        'official_package': 'com.alibaba.android.rimet',
        'package_patterns': [
            re.compile(r'com\.alibaba\.android\.rimet.*', re.IGNORECASE),
            re.compile(r'.*dingtalk.*', re.IGNORECASE),
            re.compile(r'.*rimet.*', re.IGNORECASE),
        ],
        'name_keywords': [
            '钉钉', 'DingTalk', '政务钉', '浙政钉', '粤政易',
            '赣政通', '鄂汇办', '苏政通', '豫政通', '鲁政通',
            '闽政通', '皖政通',
        ],
        'official_sites': [
            'https://www.dingtalk.com',
            'https://open.dingtalk.com',
        ],
    },
    '飞书': {
        'official_package': 'com.ss.android.lark',
        'package_patterns': [
            re.compile(r'com\.ss\.android\.lark.*', re.IGNORECASE),
            re.compile(r'.*lark.*', re.IGNORECASE),
            re.compile(r'.*feishu.*', re.IGNORECASE),
        ],
        'name_keywords': ['飞书', 'Lark', 'Feishu', '飞书办公'],
        'official_sites': [
            'https://www.feishu.cn',
            'https://open.feishu.cn',
        ],
    },
}

# ============================================================
# 搜索引擎配置
# ============================================================
SEARCH_ENGINES = {
    'baidu': {
        'name': '百度',
        'search_url': 'https://www.baidu.com/s',
        'param_key': 'wd',
        'priority': 'P0',
        'daily_limit': 2000,
        'delay_range': (2, 4),  # 秒
    },
    'bing': {
        'name': '必应',
        'search_url': 'https://cn.bing.com/search',
        'param_key': 'q',
        'priority': 'P1',
        'daily_limit': 3000,
        'delay_range': (2, 4),
    },
    'sogou': {
        'name': '搜狗',
        'search_url': 'https://www.sogou.com/web',
        'param_key': 'query',
        'priority': 'P1',
        'daily_limit': 2000,
        'delay_range': (2, 4),
    },
}

# ============================================================
# 第一级：客户名称挖掘 - 搜索关键词
# ============================================================
LEVEL1_SEARCH_KEYWORDS = {
    '企业微信': [
        '"企业微信" 客户案例',
        '"企业微信" 合作企业',
        '"企业微信" 成功案例',
        '"企业微信" 标杆客户',
        '"企业微信" 签约',
        '"企业微信" site:36kr.com',
        '"企业微信" site:zhihu.com',
        '"企业微信" 定制版 企业',
    ],
    '钉钉': [
        '"钉钉" 客户案例',
        '"钉钉" 政务版',
        '"钉钉" 定制版',
        '"钉钉" 专属版',
        '"钉钉" 客户列表',
        '"钉钉" 签约',
        '"钉钉" site:gov.cn 上线',
        '政务钉钉 上线',
    ],
    '飞书': [
        '"飞书" 企业客户',
        '"飞书" 合作案例',
        '"飞书" 使用飞书的企业',
        '"飞书" 签约 合作',
        '"飞书" 定制版',
        '"飞书" site:36kr.com',
    ],
}

# 政务类定制包搜索关键词
GOV_SEARCH_KEYWORDS = [
    '政务钉钉', '浙政钉', '粤政易', '赣政通', '鄂汇办',
    '苏政通', '豫政通', '鲁政通', '闽政通', '皖政通',
    '政务微信', '政务飞书',
    'site:gov.cn "钉钉" 定制 App 上线',
    'site:gov.cn "企业微信" 定制 App 上线',
    'site:gov.cn "飞书" 定制 App 上线',
]

# ============================================================
# 第二级：全网搜索定制包 - 搜索模板
# ============================================================
LEVEL2_SEARCH_TEMPLATES = [
    '"{enterprise}" App 安卓 下载',
    '"{enterprise}" 移动办公 App',
    '"{enterprise}" OA 客户端 Android',
    '"{enterprise}" 定制 App apk',
    'site:www.wandoujia.com "{enterprise}"',
    'site:sj.qq.com "{enterprise}"',
    '"{enterprise}" 应用商店 下载',
    '"{enterprise}" 企业微信 定制',
    '"{enterprise}" 钉钉 专属版',
    '"{enterprise}" 飞书 定制版',
]

# 企业官网常见App下载路径
ENTERPRISE_DOWNLOAD_PATHS = [
    '/download', '/app', '/mobile', '/android',
    '/about/app', '/service/download',
]

# 企业官网App下载页面关键词
ENTERPRISE_DOWNLOAD_KEYWORDS = [
    '安卓下载', 'Android', 'App下载', '扫码下载', '移动客户端',
    'APK下载', '手机版', '移动端',
]

# ============================================================
# 第三级：应用商店配置
# ============================================================
APP_STORES = {
    'huawei': {
        'name': '华为应用市场',
        'domain': 'appgallery.huawei.com',
        'search_url': 'https://appgallery.huawei.com/#/search/{keyword}',
        'priority': 'P0',
        'needs_js': True,
    },
    'xiaomi': {
        'name': '小米应用商店',
        'domain': 'app.mi.com',
        'search_url': 'https://app.mi.com/searchAll?keywords={keyword}',
        'priority': 'P0',
        'needs_js': False,
    },
    'oppo': {
        'name': 'OPPO软件商店',
        'domain': 'store.oppomobile.com',
        'search_url': 'https://store.oppomobile.com/search?q={keyword}',
        'priority': 'P0',
        'needs_js': True,
    },
    'vivo': {
        'name': 'vivo应用商店',
        'domain': 'h5.appstore.vivo.com.cn',
        'search_url': 'https://h5.appstore.vivo.com.cn/#/search?keyword={keyword}',
        'priority': 'P0',
        'needs_js': True,
    },
    'tencent': {
        'name': '应用宝',
        'domain': 'sj.qq.com',
        'search_url': 'https://sj.qq.com/search?key={keyword}',
        'priority': 'P0',
        'needs_js': True,
    },
    'wandoujia': {
        'name': '豌豆荚',
        'domain': 'www.wandoujia.com',
        'search_url': 'https://www.wandoujia.com/search?key={keyword}',
        'priority': 'P1',
        'needs_js': False,
    },
    'coolapk': {
        'name': '酷安',
        'domain': 'www.coolapk.com',
        'search_url': 'https://www.coolapk.com/search?q={keyword}',
        'priority': 'P1',
        'needs_js': True,
    },
    'apkpure': {
        'name': 'APKPure',
        'domain': 'apkpure.com',
        'search_url': 'https://apkpure.com/cn/search?q={keyword}',
        'priority': 'P1',
        'needs_js': False,
    },
}

# 商店内主动搜索关键词
STORE_SEARCH_KEYWORDS = [
    '企业微信', 'wework', '政务微信', '企微',
    '钉钉', 'DingTalk', '政务钉钉', '移动政务',
    '飞书', 'Lark', 'Feishu', '飞书办公',
    '政务办公', '移动OA', '企业办公', '协同办公',
]

# ============================================================
# 请求与反爬配置
# ============================================================
REQUEST_CONFIG = {
    'default_delay': (1, 3),        # 普通站点请求间隔（秒）
    'search_delay': (3, 5),         # 搜索引擎请求间隔（秒）
    'max_retries': 3,               # 最大重试次数
    'retry_backoff': 2,             # 重试退避因子
    'timeout': 30,                  # 请求超时（秒）
    'concurrent_requests': 4,       # 并发请求数
    'respect_robots_txt': True,     # 遵守robots.txt
}

# ============================================================
# 数据质量评分权重
# ============================================================
QUALITY_WEIGHTS = {
    'has_package_name': 0.25,
    'has_app_name': 0.15,
    'has_enterprise_name': 0.15,
    'has_version': 0.10,
    'has_developer': 0.10,
    'has_description': 0.05,
    'has_download_count': 0.05,
    'multi_source_verified': 0.15,
}

# ============================================================
# 日志配置
# ============================================================
LOG_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    'file': os.path.join(BASE_DIR, 'crawler.log'),
    'max_bytes': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5,
}
