"""
第三级爬虫 - 应用商店主动搜索入口
统一编排多个应用商店爬虫，执行关键词搜索和已有包信息补全

当前可用商店:
- 豌豆荚: 搜索+详情页均可用
- 应用宝: 仅详情页可用（/appdetail/{包名}），搜索不可用

已失效商店(API不再可用):
- 华为AppGallery: API返回403
- 小米应用商店: 页面需JS渲染，无可用API
- OPPO软件商店: API返回404
- vivo应用商店: DNS无法解析
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PRODUCT_LINES, STORE_SEARCH_KEYWORDS, APP_STORES
from storage.db import AppInfoDB
from utils.logger import get_logger

from level3_appstore.tencent_spider import TencentSpider
from level3_appstore.wandoujia_spider import WandoujiaSpider

logger = get_logger('store_searcher')


# 已知的目标产品官方包名列表（用于应用宝直接查询）
KNOWN_OFFICIAL_PACKAGES = [
    'com.tencent.wework',
    'com.alibaba.android.rimet',
    'com.ss.android.lark',
]

# 已知的定制包名列表（从公开资料收集）
KNOWN_CUSTOM_PACKAGES = [
    # 政务钉钉系列
    'com.eg.android.AlipayGphone.zjzwfw',  # 浙政钉
    'cn.gov.gd.ydzy',                       # 粤政易
    'com.hundsun.zjzwfw',                    # 浙江政务
    'cn.gov.jx.zwtb',                        # 赣政通
    'com.tencent.wework.gov',               # 政务企业微信
    'com.alibaba.android.rimet.ep',         # 钉钉专业版
    'com.alibaba.dingtalk.lwsp',            # 政务钉钉
    'com.bytedance.ee.lark',                # 飞书国际版
    # 其他可能的定制包
    'com.tencent.wecom',
]


class StoreSearcher:
    """
    应用商店主动搜索模块
    1. 用预定义关键词在可用商店搜索定制包
    2. 用已知包名在应用宝直接查询详情
    3. 用已发现的包名/应用名在各商店补全信息
    """

    def __init__(self, appinfo_db: AppInfoDB):
        self.db = appinfo_db
        self.spiders = self._init_spiders()

    def _init_spiders(self) -> list:
        """初始化可用的商店爬虫"""
        spider_classes = [
            TencentSpider,
            WandoujiaSpider,
        ]
        spiders = []
        for cls in spider_classes:
            try:
                spider = cls(self.db)
                spiders.append(spider)
                logger.info(f"初始化商店爬虫: {spider.STORE_NAME}")
            except Exception as e:
                logger.error(f"初始化 {cls.__name__} 失败: {e}")

        logger.info(
            "注意: 华为/小米/OPPO/vivo商店API已失效，"
            "仅使用豌豆荚和应用宝"
        )
        return spiders

    def run(self):
        """
        执行完整的第三级搜索流程
        1. 阶段零：已知包名直接查询应用宝
        2. 阶段一：关键词主动搜索
        3. 阶段二：已有包名交叉验证
        """
        logger.info("=" * 50)
        logger.info("第三级：应用商店检索补全 - 开始")
        logger.info("=" * 50)

        total_new = 0

        # 阶段零：用已知包名直接查应用宝
        total_new += self._phase_known_packages()

        # 阶段一：关键词主动搜索
        total_new += self._phase_keyword_search()

        # 阶段二：已有包名交叉验证
        total_new += self._phase_cross_verify()

        logger.info(f"第三级完成，新增 {total_new} 条记录")

        # 清理资源
        self._close_spiders()

    def _phase_known_packages(self) -> int:
        """
        阶段零：使用已知的官方+定制包名直接查询应用宝
        """
        logger.info("-" * 40)
        logger.info("阶段零：已知包名直接查询")
        logger.info("-" * 40)

        total_new = 0
        all_packages = KNOWN_OFFICIAL_PACKAGES + KNOWN_CUSTOM_PACKAGES

        # 找到应用宝爬虫
        tencent_spider = None
        for spider in self.spiders:
            if spider.STORE_KEY == 'tencent':
                tencent_spider = spider
                break

        if not tencent_spider:
            logger.warning("应用宝爬虫不可用，跳过已知包名查询")
            return 0

        logger.info(f"查询 {len(all_packages)} 个已知包名")

        for pkg in all_packages:
            try:
                detail = tencent_spider.get_detail_by_package(pkg)
                if detail:
                    if tencent_spider.save_app(detail, discovery_method='level3_known_package'):
                        total_new += 1
                        logger.info(f"  已知包: {pkg} -> {detail.get('app_name', '?')}")
            except Exception as e:
                logger.debug(f"  查询 {pkg} 失败: {e}")

        logger.info(f"阶段零完成，新增 {total_new} 条记录")
        return total_new

    def _phase_keyword_search(self) -> int:
        """
        阶段一：使用预定义关键词在每个商店搜索
        """
        logger.info("-" * 40)
        logger.info("阶段一：关键词主动搜索")
        logger.info("-" * 40)

        total_new = 0
        keywords = list(STORE_SEARCH_KEYWORDS)

        # 额外从产品线配置中提取关键词
        for pl_name, pl_info in PRODUCT_LINES.items():
            for kw in pl_info['name_keywords']:
                if kw not in keywords:
                    keywords.append(kw)

        logger.info(f"共 {len(keywords)} 个搜索关键词，{len(self.spiders)} 个商店")

        for spider in self.spiders:
            spider_new = 0
            logger.info(f"  搜索商店: {spider.STORE_NAME}")

            for kw in keywords:
                try:
                    results = spider.search(kw)
                    for app in results:
                        if spider.save_app(app, discovery_method='level3_keyword_search'):
                            spider_new += 1
                except Exception as e:
                    logger.error(f"  {spider.STORE_NAME} 搜索 '{kw}' 失败: {e}")

            logger.info(f"  {spider.STORE_NAME} 关键词搜索新增 {spider_new} 条")
            total_new += spider_new

        logger.info(f"阶段一完成，新增 {total_new} 条记录")
        return total_new

    def _phase_cross_verify(self) -> int:
        """
        阶段二：用已发现的包名/应用名在各商店交叉验证补全
        """
        logger.info("-" * 40)
        logger.info("阶段二：交叉验证补全")
        logger.info("-" * 40)

        total_new = 0

        # 获取已有的应用记录
        existing_apps = self.db.get_all_apps()
        if not existing_apps:
            logger.info("暂无已有应用记录，跳过交叉验证")
            return 0

        # 收集需要验证的包名和应用名
        package_names = set()
        app_names = set()
        for app in existing_apps:
            if app.get('package_name'):
                package_names.add(app['package_name'])
            if app.get('app_name'):
                name = app['app_name'].strip()
                if len(name) >= 2:
                    app_names.add(name)

        logger.info(f"已有 {len(package_names)} 个包名，{len(app_names)} 个应用名待验证")

        # 用包名在各商店搜索补全
        for spider in self.spiders:
            spider_new = 0

            # 按包名搜索（高优先级）
            for pkg in package_names:
                try:
                    results = spider.search(pkg)
                    for app in results:
                        if spider.save_app(app, discovery_method='level3_cross_verify'):
                            spider_new += 1
                except Exception as e:
                    logger.error(f"  {spider.STORE_NAME} 验证包名 '{pkg}' 失败: {e}")

            # 按应用名搜索（仅对定制包名称）
            custom_names = self._filter_custom_names(app_names)
            for name in custom_names:
                try:
                    results = spider.search(name)
                    for app in results:
                        if spider.save_app(app, discovery_method='level3_name_search'):
                            spider_new += 1
                except Exception as e:
                    logger.error(f"  {spider.STORE_NAME} 搜索应用名 '{name}' 失败: {e}")

            logger.info(f"  {spider.STORE_NAME} 交叉验证新增 {spider_new} 条")
            total_new += spider_new

        logger.info(f"阶段二完成，新增 {total_new} 条记录")
        return total_new

    def _filter_custom_names(self, app_names: set) -> list:
        """
        筛选出定制包名称（排除官方标准名称）
        只对可能是定制版的名称做搜索
        """
        official_names = set()
        for pl_info in PRODUCT_LINES.values():
            for kw in pl_info['name_keywords']:
                official_names.add(kw.lower())

        custom = []
        for name in app_names:
            name_lower = name.lower()
            # 跳过纯官方名称
            if name_lower in official_names:
                continue
            # 保留包含产品关键词但不完全等于的
            for pl_info in PRODUCT_LINES.values():
                for kw in pl_info['name_keywords']:
                    if kw.lower() in name_lower and name_lower != kw.lower():
                        custom.append(name)
                        break
                else:
                    continue
                break

        return custom[:50]  # 限制数量避免过多请求

    def _close_spiders(self):
        """关闭所有爬虫"""
        for spider in self.spiders:
            try:
                spider.close()
            except Exception:
                pass
