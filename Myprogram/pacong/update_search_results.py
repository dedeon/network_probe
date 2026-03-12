#!/usr/bin/env python3
"""
将通过搜索引擎确认的真实应用信息更新到数据库中
替换"包名推断"的数据
"""
import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from storage.db import AppInfoDB

# ============================================================
# 通过搜索引擎确认的真实应用信息
# ============================================================
CONFIRMED_APPS = {
    # 包名 -> {真实信息}
    'com.ss.android.lark.kaahyz17': {
        'app_name': 'i讯飞',
        'developer': '科大讯飞股份有限公司',
        'enterprise_name': '科大讯飞股份有限公司',
        'version': '7.18.7',
        'description': 'i讯飞APP是科大讯飞官方推出的移动办公门户，拥有即时通讯、日程管理、智能会议、协同协作等功能，帮助员工实现高效移动化办公。基于飞书定制的科大讯飞企业专属版本。',
        'source_site': '火鸟手游网',
        'source_url': 'https://www.hncj.com/sjrj/96122.html',
        'product_line': '飞书',
        'discovery_method': 'search_engine_verified',
    },
    'com.ss.android.lark.dagtjt11': {
        'app_name': '数字国投',
        'developer': '国家开发投资集团有限公司',
        'enterprise_name': '国家开发投资集团有限公司',
        'version': '7.22.10',
        'description': '数字国投APP是面向国投集团内部职工的移动办公平台，内置强大的移动OA功能，支持手机端审批、通讯录、日程会议、协同办公、移动学习等功能。基于飞书定制的国投集团企业专属版本。',
        'source_site': '安粉丝网',
        'source_url': 'https://www.anfensi.com/down/428528.html',
        'product_line': '飞书',
        'discovery_method': 'search_engine_verified',
    },
    'com.ss.android.lark.sapdl18': {
        'app_name': '胖东来',
        'developer': '胖东来商贸集团有限公司',
        'enterprise_name': '胖东来商贸集团有限公司',
        'version': '3.5.1',
        'description': '胖东来APP是胖东来集团专为内部员工打造的高效办公工具，支持多平台设备，提供日常办公、员工服务、培训发展等功能。基于飞书定制的胖东来企业专属版本。',
        'source_site': 'IT168',
        'source_url': 'https://shike.it168.com/detail/467471.html',
        'product_line': '飞书',
        'discovery_method': 'search_engine_verified',
    },
}


def main():
    db = AppInfoDB()
    conn = sqlite3.connect('output/results.db')
    c = conn.cursor()
    
    updated = 0
    inserted = 0
    
    for pkg, info in CONFIRMED_APPS.items():
        print(f"\n处理: {pkg} -> {info['app_name']}")
        
        # 检查是否存在"包名推断"记录
        rows = c.execute(
            "SELECT id, app_name, source_site FROM app_info WHERE package_name=?",
            (pkg,)
        ).fetchall()
        
        if rows:
            for row in rows:
                print(f"  找到现有记录: id={row[0]}, app_name={row[1]}, source_site={row[2]}")
            
            # 删除旧的包名推断记录
            c.execute("DELETE FROM app_info WHERE package_name=? AND source_site='包名推断'", (pkg,))
            deleted = conn.total_changes
            if deleted:
                print(f"  删除包名推断记录: {deleted}条")
            
            # 也删除小米的无效记录
            c.execute("DELETE FROM app_info WHERE package_name=? AND source_site='小米应用商店'", (pkg,))
            conn.commit()
        
        # 插入新的经过搜索引擎验证的记录
        try:
            ok = db.insert_app(
                package_name=pkg,
                app_name=info['app_name'],
                product_line=info.get('product_line', '飞书'),
                enterprise_name=info.get('enterprise_name', ''),
                developer=info.get('developer', ''),
                version=info.get('version', ''),
                version_code='',
                update_date='',
                download_count='',
                description=info.get('description', ''),
                source_site=info.get('source_site', '搜索引擎'),
                source_url=info.get('source_url', ''),
                discovery_method=info.get('discovery_method', 'search_engine_verified'),
            )
            if ok:
                inserted += 1
                print(f"  ✅ 入库成功: {info['app_name']} ({info['source_site']})")
            else:
                print(f"  ⚠️  入库失败(可能已存在)")
                # 尝试更新
                ok2 = db.update_app(
                    pkg, info['source_site'],
                    app_name=info['app_name'],
                    enterprise_name=info.get('enterprise_name', ''),
                    developer=info.get('developer', ''),
                    version=info.get('version', ''),
                    description=info.get('description', ''),
                    discovery_method='search_engine_verified',
                )
                if ok2:
                    updated += 1
                    print(f"  ✅ 更新成功")
        except Exception as e:
            print(f"  ❌ 错误: {e}")
    
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"更新结果: 新插入 {inserted} 条, 更新 {updated} 条")
    
    # 统计当前状态
    conn2 = sqlite3.connect('output/results.db')
    c2 = conn2.cursor()
    inferred = c2.execute("SELECT COUNT(*) FROM app_info WHERE source_site='包名推断'").fetchone()[0]
    verified = c2.execute("SELECT COUNT(*) FROM app_info WHERE discovery_method='search_engine_verified'").fetchone()[0]
    total = c2.execute("SELECT COUNT(*) FROM app_info").fetchone()[0]
    print(f"\n当前数据库状态:")
    print(f"  总记录数: {total}")
    print(f"  搜索引擎验证: {verified}")
    print(f"  仍为包名推断: {inferred}")
    
    # 列出仍然是包名推断的记录
    rows = c2.execute("SELECT package_name, app_name FROM app_info WHERE source_site='包名推断' ORDER BY package_name").fetchall()
    print(f"\n仍为包名推断的 {len(rows)} 条记录:")
    for pkg, name in rows:
        print(f"  {pkg} -> {name}")
    
    conn2.close()
    
    # 导出
    print("\n执行质量评分和导出...")
    try:
        from pipeline.quality_scorer import QualityScorer
        from storage.db import CustomerDB
        from storage.exporter import DataExporter
        QualityScorer(db).run()
        cdb = CustomerDB()
        exp = DataExporter(cdb, db)
        for nm, pa in exp.export_all().items():
            print(f"  导出: {nm} -> {pa}")
        cdb.close()
    except Exception as e:
        print(f"导出失败: {e}")
    
    db.close()
    print("\n完成!")


if __name__ == '__main__':
    main()
