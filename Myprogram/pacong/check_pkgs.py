#!/usr/bin/env python3
"""检查用户指定的包名是否已在数据库中"""
import sqlite3

# 用户提供的飞书定制包
FEISHU_PKGS = [
    'com.ss.android.lark', 'com.ss.android.lark.lite', 'com.ss.android.lark.ka31',
    'com.ss.android.lark.kaahyz17', 'com.ss.android.lark.kacrc', 'com.ss.android.lark.kahzyx88',
    'com.ss.android.lark.kami', 'com.ss.android.lark.kazdtq', 'com.ss.android.lark.kazsy73',
    'com.ss.android.lark.dabcsy97', 'com.ss.android.lark.dagtjt11', 'com.ss.android.lark.dahngd31',
    'com.ss.android.lark.dai39dl9', 'com.ss.android.lark.dajzjt26', 'com.ss.android.lark.dajzkx436',
    'com.ss.android.lark.dastw29', 'com.ss.android.lark.greentown', 'com.ss.android.lark.hongyuntong',
    'com.ss.android.lark.htone', 'com.ss.android.lark.ihaier', 'com.ss.android.lark.jxlh',
    'com.ss.android.lark.mdzh', 'com.ss.android.lark.pls', 'com.ss.android.lark.rongchuang',
    'com.ss.android.lark.sa83b7j6', 'com.ss.android.lark.sacbdn67new', 'com.ss.android.lark.sahlzj17',
    'com.ss.android.lark.samhzo3j', 'com.ss.android.lark.sapdl18', 'com.ss.android.lark.sarq2tpv',
    'com.ss.android.lark.saxdz51', 'com.ss.android.lark.saxmsa', 'com.ss.android.lark.saxmsa667',
    'com.ss.android.lark.weifu', 'com.ss.android.lark.ce', 'com.ss.android.lark.kacf',
    'com.ss.android.lark.kacw', 'com.ss.android.lark.sc', 'com.ss.android.lark.kalanhe',
    'com.ss.android.lark.kanewhope',
]

# 用户提供的钉钉定制包
DINGDING_PKGS = [
    'com.alibaba.android.rimet', 'com.alibaba.android.rimet.adt', 'com.alibaba.android.rimet.aliding',
    'com.alibaba.android.rimet.bgyfw', 'com.alibaba.android.rimet.bitding', 'com.alibaba.android.rimet.catlcome',
    'com.alibaba.android.rimet.ccflink', 'com.alibaba.android.rimet.czd', 'com.alibaba.android.rimet.diswu',
    'com.alibaba.android.rimet.faw_easy', 'com.alibaba.android.rimet.fdyfn', 'com.alibaba.android.rimet.fosun',
    'com.alibaba.android.rimet.rimm', 'com.alibaba.android.rimet.zj', 'com.alibaba.android.rimet.edu',
]

# 用户提供的钉钉政务版(浙政钉等)
TAURUS_PKGS = [
    'com.alibaba.taurus', 'com.alibaba.taurus.changchun', 'com.alibaba.taurus.chongqing',
    'com.alibaba.taurus.cpic', 'com.alibaba.taurus.fujian', 'com.alibaba.taurus.hainan',
    'com.alibaba.taurus.hainanxc', 'com.alibaba.taurus.hengdadingems', 'com.alibaba.taurus.jiangxi',
    'com.alibaba.taurus.ningxia', 'com.alibaba.taurus.ningxianew', 'com.alibaba.taurus.qzt',
    'com.alibaba.taurus.xxxs', 'com.alibaba.taurus.zhejiang', 'com.alibaba.taurus.zhengzhou',
    'com.alibaba.taurus.anhui',
]

ALL_PKGS = FEISHU_PKGS + DINGDING_PKGS + TAURUS_PKGS

conn = sqlite3.connect('output/results.db')
c = conn.cursor()

existing = set()
for row in c.execute('SELECT package_name FROM app_info'):
    existing.add(row[0])

print(f"数据库总记录: {len(existing)} 条")
print()

for label, pkgs in [("飞书定制包", FEISHU_PKGS), ("钉钉定制包", DINGDING_PKGS), ("浙政钉/taurus", TAURUS_PKGS)]:
    found = [p for p in pkgs if p in existing]
    missing = [p for p in pkgs if p not in existing]
    print(f"=== {label} ({len(found)}/{len(pkgs)} 已爬到) ===")
    for p in found:
        print(f"  ✅ {p}")
    for p in missing:
        print(f"  ❌ {p}")
    print()

all_found = [p for p in ALL_PKGS if p in existing]
all_missing = [p for p in ALL_PKGS if p not in existing]
print(f"=== 汇总: 已爬到 {len(all_found)}/{len(ALL_PKGS)}, 缺失 {len(all_missing)} ===")

conn.close()
