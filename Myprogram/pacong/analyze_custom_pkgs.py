#!/usr/bin/env python3
"""分析所有定制包的类型和使用场景"""
import sqlite3
import json

conn = sqlite3.connect('output/results.db')
c = conn.cursor()

data = {}

# 1. 飞书定制包
rows = c.execute("""SELECT package_name, app_name, enterprise_name, source_site, discovery_method 
    FROM app_info WHERE package_name LIKE 'com.ss.android.lark.%' 
    ORDER BY package_name""").fetchall()
data['feishu'] = [{'pkg': r[0], 'name': r[1], 'ent': r[2], 'source': r[3], 'method': r[4]} for r in rows]

# 2. 钉钉rimet定制包
rows = c.execute("""SELECT package_name, app_name, enterprise_name, source_site, discovery_method 
    FROM app_info WHERE package_name LIKE 'com.alibaba.android.rimet.%' 
    ORDER BY package_name""").fetchall()
data['dingding'] = [{'pkg': r[0], 'name': r[1], 'ent': r[2], 'source': r[3], 'method': r[4]} for r in rows]

# 3. 政务钉钉taurus
rows = c.execute("""SELECT package_name, app_name, enterprise_name, source_site, discovery_method 
    FROM app_info WHERE package_name LIKE 'com.alibaba.taurus.%' 
    ORDER BY package_name""").fetchall()
data['taurus'] = [{'pkg': r[0], 'name': r[1], 'ent': r[2], 'source': r[3], 'method': r[4]} for r in rows]

# 4. 企业微信相关
rows = c.execute("""SELECT package_name, app_name, enterprise_name, source_site, discovery_method 
    FROM app_info WHERE package_name IN (
        'com.tencent.wework', 'com.tencent.weworkenterprise', 'com.tencent.weworklocal'
    ) ORDER BY package_name""").fetchall()
data['wecom'] = [{'pkg': r[0], 'name': r[1], 'ent': r[2], 'source': r[3], 'method': r[4]} for r in rows]

# 5. 各product_line统计
rows = c.execute("""SELECT product_line, COUNT(*) FROM app_info 
    GROUP BY product_line ORDER BY COUNT(*) DESC""").fetchall()
data['product_line_stats'] = [{'pl': r[0], 'count': r[1]} for r in rows]

# 6. discovery_method统计
rows = c.execute("""SELECT discovery_method, COUNT(*) FROM app_info 
    GROUP BY discovery_method ORDER BY COUNT(*) DESC""").fetchall()
data['method_stats'] = [{'method': r[0], 'count': r[1]} for r in rows]

# 7. 总记录数
data['total'] = c.execute('SELECT COUNT(*) FROM app_info').fetchone()[0]

# 打印汇总
print(f"总记录数: {data['total']}")
print(f"\n飞书定制包: {len(data['feishu'])}")
for d in data['feishu']:
    print(f"  {d['pkg']} | {d['name']} | {d['ent']} | {d['method']}")

print(f"\n钉钉定制包: {len(data['dingding'])}")
for d in data['dingding']:
    print(f"  {d['pkg']} | {d['name']} | {d['ent']} | {d['method']}")

print(f"\n政务钉钉(taurus)定制包: {len(data['taurus'])}")
for d in data['taurus']:
    print(f"  {d['pkg']} | {d['name']} | {d['ent']} | {d['method']}")

print(f"\n企业微信: {len(data['wecom'])}")
for d in data['wecom']:
    print(f"  {d['pkg']} | {d['name']} | {d['ent']} | {d['method']}")

print(f"\n产品线统计:")
for d in data['product_line_stats']:
    print(f"  {d['pl']}: {d['count']}")

print(f"\n数据来源方法统计:")
for d in data['method_stats']:
    print(f"  {d['method']}: {d['count']}")

# 保存json以备报告生成使用
with open('output/analysis_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("\n数据已保存到 output/analysis_data.json")

conn.close()
