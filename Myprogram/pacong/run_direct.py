#!/usr/bin/env python3
"""运行直接爬虫 - 带强制刷新输出"""
import sys
import os

# 强制行缓冲
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

print("启动直接爬虫...", flush=True)

from direct_crawler import DirectCrawler, KNOWN_APPS
print(f"已知应用列表: {len(KNOWN_APPS)} 个", flush=True)

crawler = DirectCrawler()

# 清理旧数据
crawler._clean_old_data()
print("旧数据已清理", flush=True)

# 阶段1: 应用宝批量验证
print("\n=== 阶段1: 应用宝详情页批量验证 ===", flush=True)
crawler._phase1_yingyongbao_verify()
count1 = crawler.db.count()
print(f"阶段1完成: {count1} 条记录", flush=True)

# 阶段2: APKPure搜索 (可能被403，跳过也可以)
print("\n=== 阶段2: APKPure搜索 ===", flush=True)
try:
    crawler._phase2_apkpure_search()
except Exception as e:
    print(f"阶段2跳过: {e}", flush=True)
count2 = crawler.db.count()
print(f"阶段2完成: {count2} 条记录", flush=True)

# 阶段3: 搜索引擎
print("\n=== 阶段3: 搜索引擎补充 ===", flush=True)
try:
    crawler._phase3_search_engine()
except Exception as e:
    print(f"阶段3跳过: {e}", flush=True)
count3 = crawler.db.count()
print(f"阶段3完成: {count3} 条记录", flush=True)

# 数据处理和导出
print("\n=== 数据处理和导出 ===", flush=True)
if count3 > 0:
    from storage.db import CustomerDB
    from storage.exporter import DataExporter
    from pipeline.quality_scorer import QualityScorer
    
    scorer = QualityScorer(crawler.db)
    scorer.run()
    print("质量评分完成", flush=True)
    
    customer_db = CustomerDB()
    exporter = DataExporter(customer_db, crawler.db)
    paths = exporter.export_all()
    print("导出完成:", flush=True)
    for name, path in paths.items():
        print(f"  {name} → {path}", flush=True)
    
    exporter.print_summary()
    customer_db.close()

crawler.close()
print("\n全部完成!", flush=True)
