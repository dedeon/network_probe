"""项目整体统计信息收集"""
import sqlite3, os

# 数据库统计
conn = sqlite3.connect('output/results.db')
c = conn.cursor()

print('=== 数据库最终统计 ===')
total = c.execute('SELECT COUNT(*) FROM app_info').fetchone()[0]
print(f'总记录数: {total}')

print('\n=== 各产品线记录数 ===')
rows = c.execute('SELECT product_line, COUNT(*) FROM app_info GROUP BY product_line ORDER BY COUNT(*) DESC').fetchall()
for pl, cnt in rows:
    print(f'  {pl}: {cnt}')

print('\n=== 各数据源记录数 ===')
rows = c.execute('SELECT source_site, COUNT(*) FROM app_info GROUP BY source_site ORDER BY COUNT(*) DESC').fetchall()
for ss, cnt in rows:
    print(f'  {ss}: {cnt}')

print('\n=== 各发现方式记录数 ===')
rows = c.execute('SELECT discovery_method, COUNT(*) FROM app_info GROUP BY discovery_method ORDER BY COUNT(*) DESC').fetchall()
for dm, cnt in rows:
    print(f'  {dm}: {cnt}')

print('\n=== 数据质量评分分布 ===')
rows = c.execute('''SELECT 
    CASE 
        WHEN quality_score >= 0.8 THEN 'A级(>=0.8)'
        WHEN quality_score >= 0.6 THEN 'B级(0.6-0.8)'
        WHEN quality_score >= 0.4 THEN 'C级(0.4-0.6)'
        ELSE 'D级(<0.4)'
    END as grade, COUNT(*) 
    FROM app_info GROUP BY grade ORDER BY grade''').fetchall()
for grade, cnt in rows:
    print(f'  {grade}: {cnt}')

avg_score = c.execute('SELECT AVG(quality_score) FROM app_info').fetchone()[0]
print(f'  平均评分: {avg_score:.4f}')

# 定制包统计
print('\n=== 定制包数量 ===')
feishu = c.execute("SELECT COUNT(*) FROM app_info WHERE package_name LIKE 'com.ss.android.lark.%'").fetchone()[0]
dingtalk = c.execute("SELECT COUNT(*) FROM app_info WHERE package_name LIKE 'com.alibaba.android.rimet.%'").fetchone()[0]
taurus = c.execute("SELECT COUNT(*) FROM app_info WHERE package_name LIKE 'com.alibaba.taurus.%'").fetchone()[0]
wework = c.execute("SELECT COUNT(*) FROM app_info WHERE package_name LIKE 'com.tencent.wework%'").fetchone()[0]
print(f'  飞书定制包: {feishu}')
print(f'  钉钉定制包: {dingtalk}')
print(f'  专有钉钉定制包: {taurus}')
print(f'  企业微信相关: {wework}')

conn.close()

# 客户数据库统计
if os.path.exists('output/customers.db'):
    conn2 = sqlite3.connect('output/customers.db')
    c2 = conn2.cursor()
    try:
        cust_count = c2.execute('SELECT COUNT(*) FROM customers').fetchone()[0]
        print(f'\n=== 客户数据库 ===')
        print(f'  客户记录数: {cust_count}')
    except:
        print('\n客户数据库表不存在或为空')
    conn2.close()

# 文件统计
print('\n=== 输出文件 ===')
for f in sorted(os.listdir('output')):
    fpath = os.path.join('output', f)
    size = os.path.getsize(fpath)
    if size > 1024*1024:
        print(f'  {f}: {size/1024/1024:.1f}MB')
    elif size > 1024:
        print(f'  {f}: {size/1024:.1f}KB')
    else:
        print(f'  {f}: {size}B')

# Python代码行数统计
print('\n=== 代码统计 ===')
total_lines = 0
total_files = 0
module_stats = {}
for root, dirs, files in os.walk('.'):
    if '__pycache__' in root:
        continue
    for f in files:
        if f.endswith('.py'):
            fpath = os.path.join(root, f)
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fp:
                lines = len(fp.readlines())
                total_lines += lines
                total_files += 1
                # 模块统计
                parts = root.split('/')
                module = parts[1] if len(parts) > 1 else '根目录'
                module_stats[module] = module_stats.get(module, {'files': 0, 'lines': 0})
                module_stats[module]['files'] += 1
                module_stats[module]['lines'] += lines

print(f'  Python文件总数: {total_files}')
print(f'  Python代码总行数: {total_lines}')
print('\n  各模块统计:')
for mod, stats in sorted(module_stats.items()):
    print(f'    {mod}: {stats["files"]}个文件, {stats["lines"]}行')
