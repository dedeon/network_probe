#!/usr/bin/env python3
"""
批量更新：通过搜索引擎确认的真实应用信息
替换数据库中"包名推断"的旧数据

搜索方法：使用 web_search 工具在搜索引擎上搜索每个包名，
在第三方APK下载站（hncj.com, anfensi.com, downxia.com, 9663.com, it168.com等）
找到真实的应用详情页，确认包名、应用名、开发者等信息。
"""
import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from storage.db import AppInfoDB

# ============================================================
# 通过搜索引擎确认的真实应用信息（第二批）
# ============================================================
CONFIRMED_APPS = {
    # ===== 政务钉钉(taurus)系列 =====
    'com.alibaba.taurus.jiangxi': {
        'app_name': '赣政通',
        'developer': '江西省大数据中心',
        'enterprise_name': '江西省大数据中心',
        'version': '2.8.0.9',
        'description': '赣政通APP是江西省官方政务服务软件，由阿里云政务钉钉联合江西省政府打造。提供公文查询、事项审批、协同办公、会议管理等功能，整合公安、医保、社保等高频便民事项。采用国密算法端到端加密，使用江西政务云存储。基于政务钉钉定制的江西省专属版本。',
        'source_site': '当下软件园',
        'source_url': 'https://www.downxia.com/downinfo/443455.html',
        'product_line': '钉钉',
        'discovery_method': 'search_engine_verified',
    },
    'com.alibaba.taurus.cpic': {
        'app_name': '太好钉',
        'developer': '钉钉科技有限公司',
        'enterprise_name': '中国太平洋保险(集团)股份有限公司',
        'version': '2.12.24',
        'description': '太好钉APP是专为太平洋保险集团打造的专用办公平台，整合完整的工作台功能。通过扁平化协同平台，提高办公效率、提升组织协同水平、促进组织效能提升，成为组织数字化基座。基于政务钉钉(专有钉钉)定制的太平洋保险企业专属版本。',
        'source_site': '安粉丝网',
        'source_url': 'http://www.anfensi.com/down/429077.html',
        'product_line': '钉钉',
        'discovery_method': 'search_engine_verified',
    },
    'com.alibaba.taurus.qzt': {
        'app_name': '秦政通',
        'developer': '陕西省政务大数据服务中心',
        'enterprise_name': '陕西省政务大数据服务中心',
        'version': '8.3.1081',
        'description': '秦政通是陕西省一体化协同办公平台的手机客户端，提供公文查询、内部通讯录、日志写作、考勤考核、审批、日程管理等功能。利用人工智能、大数据等技术提供智能化服务，已导入8万用户，对接14项共性业务。基于政务钉钉定制的陕西省专属版本。',
        'source_site': 'IT168',
        'source_url': 'https://shike.it168.com/detail/366613.html',
        'product_line': '钉钉',
        'discovery_method': 'search_engine_verified',
    },

    # ===== 钉钉定制版(rimet)系列 =====
    'com.alibaba.android.rimet.aliding': {
        'app_name': '阿里钉',
        'developer': '阿里巴巴集团',
        'enterprise_name': '阿里巴巴集团',
        'version': '6.5.56',
        'description': '阿里钉是阿里巴巴集团内部专用的办公软件。基于钉钉开发框架，为阿里巴巴用户提供一站式办公服务，集成即时通讯、任务管理、日程安排、考勤签到、审批等功能，支持企业通讯录导入和视频电话会议。基于钉钉定制的阿里巴巴内部专属版本。',
        'source_site': 'IT168',
        'source_url': 'https://shike.it168.com/detail/309410.html',
        'product_line': '钉钉',
        'discovery_method': 'search_engine_verified',
    },
    'com.alibaba.android.rimet.ccflink': {
        'app_name': 'CCFLink',
        'developer': '中国计算机学会(CCF)',
        'enterprise_name': '中国计算机学会(CCF)',
        'version': '',
        'description': 'CCFLink是中国计算机学会(CCF)与钉钉合作推出的数字化平台，是CCF的专属钉钉。用于提升CCF数字化水平，探索全新会员服务模式。基于钉钉定制的中国计算机学会专属版本。',
        'source_site': '极客公园',
        'source_url': 'https://www.geekpark.net/news/316707',
        'product_line': '钉钉',
        'discovery_method': 'search_engine_verified',
    },

    # ===== 飞书定制版(lark)系列 =====
    'com.ss.android.lark.htone': {
        'app_name': '华通3.0',
        'developer': '华住集团',
        'enterprise_name': '华住集团有限公司',
        'version': '6.5.9',
        'description': '华通3.0（HTone）是华住集团专属的企业办公软件。设有实时通讯栏目，展示组织架构实现零障碍跨部门沟通，提供差旅通、云学堂、签到考勤、移动审批等数十种常用工具。基于飞书定制的华住集团企业专属版本。',
        'source_site': '火鸟手游网',
        'source_url': 'http://www.hncj.com/sjrj/106972.html',
        'product_line': '飞书',
        'discovery_method': 'search_engine_verified',
    },
}

# ============================================================
# 搜索后确认包名推断基本正确，但无法找到独立下载页的包名
# 这些通过新闻报道/企业公告间接确认企业确实使用定制版
# source_site 改为"新闻报道确认"
# ============================================================
NEWS_CONFIRMED_APPS = {
    'com.alibaba.android.rimet.bgyfw': {
        'app_name': '碧桂园服务钉钉',
        'enterprise_name': '碧桂园服务控股有限公司',
        'description': '碧桂园服务专属钉钉，首期10万人上线。阿里云为碧桂园服务提供企业专属钉钉，围绕智慧物业管理、数字社区等方面展开深度合作。',
        'source_site': '新闻报道确认',
        'source_url': 'https://sh.house.163.com/21/0728/17/GG0PUQQA00078746.html',
        'product_line': '钉钉',
        'discovery_method': 'news_verified',
    },
    'com.alibaba.android.rimet.catlcome': {
        'app_name': '宁德时代钉钉',
        'enterprise_name': '宁德时代新能源科技股份有限公司',
        'description': '宁德时代专属钉钉（COME）。宁德时代全球十万员工使用钉钉专属版进行协同办公，打通现有应用与系统实现高效数智化运作。',
        'source_site': '新闻报道确认',
        'source_url': 'https://news.duote.com/202411/705942.html',
        'product_line': '钉钉',
        'discovery_method': 'news_verified',
    },
}


def main():
    db = AppInfoDB()
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'results.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    updated = 0
    inserted = 0
    news_updated = 0

    print("=" * 60)
    print("第一部分：搜索引擎直接确认的应用信息")
    print("=" * 60)

    for pkg, info in CONFIRMED_APPS.items():
        print(f"\n处理: {pkg} -> {info['app_name']}")

        # 检查是否存在旧记录
        rows = c.execute(
            "SELECT id, app_name, source_site FROM app_info WHERE package_name=?",
            (pkg,)
        ).fetchall()

        if rows:
            for row in rows:
                print(f"  找到现有记录: id={row[0]}, app_name={row[1]}, source_site={row[2]}")

            # 删除旧的包名推断记录
            c.execute("DELETE FROM app_info WHERE package_name=? AND source_site='包名推断'", (pkg,))
            deleted_count = c.rowcount
            if deleted_count:
                print(f"  删除包名推断记录: {deleted_count}条")

            # 也删除小米的无效记录
            c.execute("DELETE FROM app_info WHERE package_name=? AND source_site='小米应用商店'", (pkg,))
            # 也删除搜狗搜索的垃圾数据
            c.execute("DELETE FROM app_info WHERE package_name=? AND source_site='搜狗搜索'", (pkg,))
            conn.commit()

        # 插入新的经过搜索引擎验证的记录
        try:
            ok = db.insert_app(
                package_name=pkg,
                app_name=info['app_name'],
                product_line=info.get('product_line', '钉钉'),
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
                print(f"  ⚠️  记录已存在，尝试更新")
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

    print(f"\n{'=' * 60}")
    print("第二部分：新闻报道间接确认的应用信息")
    print("=" * 60)

    for pkg, info in NEWS_CONFIRMED_APPS.items():
        print(f"\n处理: {pkg} -> {info['app_name']}")

        # 删除旧的包名推断记录
        c.execute("DELETE FROM app_info WHERE package_name=? AND source_site='包名推断'", (pkg,))
        deleted_count = c.rowcount
        if deleted_count:
            print(f"  删除包名推断记录: {deleted_count}条")
            conn.commit()

        try:
            ok = db.insert_app(
                package_name=pkg,
                app_name=info['app_name'],
                product_line=info.get('product_line', '钉钉'),
                enterprise_name=info.get('enterprise_name', ''),
                developer='',
                version='',
                version_code='',
                update_date='',
                download_count='',
                description=info.get('description', ''),
                source_site=info['source_site'],
                source_url=info.get('source_url', ''),
                discovery_method=info.get('discovery_method', 'news_verified'),
            )
            if ok:
                news_updated += 1
                print(f"  ✅ 入库成功: {info['app_name']} ({info['source_site']})")
            else:
                ok2 = db.update_app(
                    pkg, info['source_site'],
                    app_name=info['app_name'],
                    enterprise_name=info.get('enterprise_name', ''),
                    description=info.get('description', ''),
                    discovery_method=info.get('discovery_method', 'news_verified'),
                )
                if ok2:
                    news_updated += 1
                    print(f"  ✅ 更新成功")
        except Exception as e:
            print(f"  ❌ 错误: {e}")

    conn.close()

    print(f"\n{'=' * 60}")
    print(f"更新结果: 新插入 {inserted} 条, 更新 {updated} 条, 新闻确认 {news_updated} 条")

    # 统计当前状态
    conn2 = sqlite3.connect(db_path)
    c2 = conn2.cursor()
    inferred = c2.execute("SELECT COUNT(*) FROM app_info WHERE source_site='包名推断'").fetchone()[0]
    verified = c2.execute("SELECT COUNT(*) FROM app_info WHERE discovery_method='search_engine_verified'").fetchone()[0]
    news_v = c2.execute("SELECT COUNT(*) FROM app_info WHERE discovery_method='news_verified'").fetchone()[0]
    total = c2.execute("SELECT COUNT(*) FROM app_info").fetchone()[0]
    print(f"\n当前数据库状态:")
    print(f"  总记录数: {total}")
    print(f"  搜索引擎验证: {verified}")
    print(f"  新闻报道验证: {news_v}")
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
