"""
企业IM安卓客户端包信息爬虫 - 主程序入口
三级递进式搜索策略流水线编排
"""
import argparse
import sys
import time

from config import OUTPUT_DIR
from storage.db import CustomerDB, AppInfoDB
from storage.exporter import DataExporter
from utils.logger import setup_logger, get_logger

logger = get_logger('main')


class CrawlerScheduler:
    """
    爬虫调度器
    编排三级流水线的执行顺序
    """

    def __init__(self):
        self.customer_db = CustomerDB()
        self.appinfo_db = AppInfoDB()
        self.exporter = DataExporter(self.customer_db, self.appinfo_db)

    def run_level1(self):
        """
        第一级：客户名称挖掘
        从产品官网、搜索引擎、媒体报道、政务平台挖掘客户名称
        """
        logger.info("=" * 60)
        logger.info("开始执行 第一级：客户名称挖掘")
        logger.info("=" * 60)

        from level1_customers.official_site_spider import OfficialSiteSpider
        from level1_customers.search_customer_spider import SearchCustomerSpider
        from level1_customers.gov_spider import GovSpider
        from level1_customers.news_spider import NewsSpider

        spiders = [
            ('官网案例爬虫', OfficialSiteSpider(self.customer_db)),
            ('搜索引擎客户挖掘', SearchCustomerSpider(self.customer_db)),
            ('政务平台爬虫', GovSpider(self.customer_db)),
            ('媒体报道爬虫', NewsSpider(self.customer_db)),
        ]

        for name, spider in spiders:
            try:
                logger.info(f"运行: {name}")
                spider.run()
                logger.info(f"{name} 完成")
            except Exception as e:
                logger.error(f"{name} 执行失败: {e}")

        count = self.customer_db.count()
        logger.info(f"第一级完成，共挖掘 {count} 条客户记录")

    def run_level2(self):
        """
        第二级：全网定制包搜索
        以客户名称为线索，全网搜索定制安卓客户端
        """
        logger.info("=" * 60)
        logger.info("开始执行 第二级：全网定制包搜索")
        logger.info("=" * 60)

        from level2_fullweb.search_engine_spider import SearchEnginePackageSpider
        from level2_fullweb.enterprise_site_spider import EnterpriseSiteSpider
        from level2_fullweb.apk_site_spider import APKSiteSpider

        customers = self.customer_db.get_all_customers()
        logger.info(f"从客户库加载 {len(customers)} 条客户记录")

        spiders = [
            ('搜索引擎包搜索', SearchEnginePackageSpider(self.appinfo_db, customers)),
            ('企业官网扫描', EnterpriseSiteSpider(self.appinfo_db, customers)),
            ('APK站点爬虫', APKSiteSpider(self.appinfo_db)),
        ]

        for name, spider in spiders:
            try:
                logger.info(f"运行: {name}")
                spider.run()
                logger.info(f"{name} 完成")
            except Exception as e:
                logger.error(f"{name} 执行失败: {e}")

        count = self.appinfo_db.count()
        logger.info(f"第二级完成，当前共 {count} 条应用记录")

    def run_level3(self):
        """
        第三级：应用商店检索补全
        在各大应用商店中检索补全包信息
        """
        logger.info("=" * 60)
        logger.info("开始执行 第三级：应用商店检索补全")
        logger.info("=" * 60)

        from level3_appstore.store_searcher import StoreSearcher

        searcher = StoreSearcher(self.appinfo_db)
        try:
            searcher.run()
        except Exception as e:
            logger.error(f"应用商店检索失败: {e}")

        count = self.appinfo_db.count()
        logger.info(f"第三级完成，当前共 {count} 条应用记录")

    def run_pipeline(self):
        """运行数据处理管道"""
        logger.info("=" * 60)
        logger.info("开始执行 数据处理管道")
        logger.info("=" * 60)

        from pipeline.dedup import Deduplicator
        from pipeline.cleaner import DataCleaner
        from pipeline.enterprise_extractor import EnterpriseExtractor
        from pipeline.classifier import ProductClassifier
        from pipeline.quality_scorer import QualityScorer

        processors = [
            ('去重处理', Deduplicator(self.appinfo_db)),
            ('数据清洗', DataCleaner(self.appinfo_db)),
            ('企业名称提取', EnterpriseExtractor(self.appinfo_db)),
            ('产品线分类', ProductClassifier(self.appinfo_db)),
            ('质量评分', QualityScorer(self.appinfo_db)),
        ]

        for name, processor in processors:
            try:
                logger.info(f"运行: {name}")
                processor.run()
                logger.info(f"{name} 完成")
            except Exception as e:
                logger.error(f"{name} 执行失败: {e}")

    def export_results(self):
        """导出结果"""
        logger.info("=" * 60)
        logger.info("开始导出结果")
        logger.info("=" * 60)

        paths = self.exporter.export_all()
        for name, path in paths.items():
            logger.info(f"已导出: {name} → {path}")

        self.exporter.print_summary()

    def run_all(self):
        """执行完整的三级流水线"""
        start_time = time.time()
        logger.info("=" * 60)
        logger.info("  企业IM安卓客户端包信息爬虫 - 开始执行")
        logger.info("=" * 60)

        self.run_level1()
        self.run_level2()
        self.run_level3()
        self.run_pipeline()
        self.export_results()

        elapsed = time.time() - start_time
        logger.info(f"全部完成，耗时 {elapsed / 60:.1f} 分钟")

    def close(self):
        self.customer_db.close()
        self.appinfo_db.close()
        from utils.http_client import http_client
        http_client.close()


def main():
    parser = argparse.ArgumentParser(
        description='企业IM安卓客户端包信息爬虫',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  python main.py                    # 执行完整三级流水线
  python main.py --level 1          # 仅执行第一级：客户名称挖掘
  python main.py --level 2          # 仅执行第二级：全网搜索定制包
  python main.py --level 3          # 仅执行第三级：应用商店补全
  python main.py --pipeline         # 仅执行数据处理管道
  python main.py --export           # 仅导出结果
  python main.py --level 1 2        # 执行第一级和第二级
        '''
    )
    parser.add_argument(
        '--level', nargs='+', type=int, choices=[1, 2, 3],
        help='指定执行的爬虫级别（1/2/3），可多选'
    )
    parser.add_argument(
        '--pipeline', action='store_true',
        help='仅执行数据处理管道'
    )
    parser.add_argument(
        '--export', action='store_true',
        help='仅导出结果'
    )

    args = parser.parse_args()

    # 初始化日志
    setup_logger()

    scheduler = CrawlerScheduler()

    try:
        if args.pipeline:
            scheduler.run_pipeline()
            scheduler.export_results()
        elif args.export:
            scheduler.export_results()
        elif args.level:
            for level in sorted(args.level):
                if level == 1:
                    scheduler.run_level1()
                elif level == 2:
                    scheduler.run_level2()
                elif level == 3:
                    scheduler.run_level3()
            scheduler.run_pipeline()
            scheduler.export_results()
        else:
            scheduler.run_all()
    except KeyboardInterrupt:
        logger.info("用户中断执行")
    finally:
        scheduler.close()


if __name__ == '__main__':
    main()
