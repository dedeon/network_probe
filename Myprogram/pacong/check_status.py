import sqlite3
conn = sqlite3.connect('output/results.db')
c = conn.cursor()

# 所有定制包 (排除标准版)
standard_pkgs = ['com.ss.android.lark', 'com.alibaba.android.rimet', 'com.alibaba.taurus']

print('=== 飞书(lark)定制包 ===')
rows = c.execute("""SELECT package_name, app_name, source_site, discovery_method 
    FROM app_info WHERE package_name LIKE 'com.ss.android.lark.%' 
    ORDER BY package_name""").fetchall()
for pkg, name, site, disc in rows:
    suffix = pkg.replace('com.ss.android.lark.', '')
    print(f'  {suffix:20s} -> {name:30s} | {site:15s} | {disc}')
print(f'小计: {len(rows)}')

print('\n=== 钉钉(rimet)定制包 ===')
rows = c.execute("""SELECT package_name, app_name, source_site, discovery_method 
    FROM app_info WHERE package_name LIKE 'com.alibaba.android.rimet.%' 
    ORDER BY package_name""").fetchall()
for pkg, name, site, disc in rows:
    suffix = pkg.replace('com.alibaba.android.rimet.', '')
    print(f'  {suffix:20s} -> {name:30s} | {site:15s} | {disc}')
print(f'小计: {len(rows)}')

print('\n=== 政务钉钉(taurus)定制包 ===')
rows = c.execute("""SELECT package_name, app_name, source_site, discovery_method 
    FROM app_info WHERE package_name LIKE 'com.alibaba.taurus.%' 
    ORDER BY package_name""").fetchall()
for pkg, name, site, disc in rows:
    suffix = pkg.replace('com.alibaba.taurus.', '')
    print(f'  {suffix:20s} -> {name:30s} | {site:15s} | {disc}')
print(f'小计: {len(rows)}')

conn.close()
