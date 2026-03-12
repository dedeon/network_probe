#!/usr/bin/env python3
"""
专门爬取用户指定的定制安卓包（飞书/钉钉/浙政钉）
策略:
1. 先在应用宝上全量测试68个缺失包名
2. 能爬到的直接入库
3. 404的记录下来，输出报告
"""
import httpx
import re
import json
import time
import random
import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from storage.db import AppInfoDB

# ============================================================
# 68个缺失的定制包名
# ============================================================
CUSTOM_PKGS = {
    '飞书': [
        'com.ss.android.lark.lite', 'com.ss.android.lark.ka31',
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
    ],
    '钉钉': [
        'com.alibaba.android.rimet.adt', 'com.alibaba.android.rimet.aliding',
        'com.alibaba.android.rimet.bgyfw', 'com.alibaba.android.rimet.bitding', 'com.alibaba.android.rimet.catlcome',
        'com.alibaba.android.rimet.ccflink', 'com.alibaba.android.rimet.czd', 'com.alibaba.android.rimet.diswu',
        'com.alibaba.android.rimet.faw_easy', 'com.alibaba.android.rimet.fdyfn', 'com.alibaba.android.rimet.fosun',
        'com.alibaba.android.rimet.rimm', 'com.alibaba.android.rimet.zj', 'com.alibaba.android.rimet.edu',
    ],
    '钉钉': [  # taurus 也归入钉钉（政务版钉钉）
        'com.alibaba.android.rimet.adt', 'com.alibaba.android.rimet.aliding',
        'com.alibaba.android.rimet.bgyfw', 'com.alibaba.android.rimet.bitding', 'com.alibaba.android.rimet.catlcome',
        'com.alibaba.android.rimet.ccflink', 'com.alibaba.android.rimet.czd', 'com.alibaba.android.rimet.diswu',
        'com.alibaba.android.rimet.faw_easy', 'com.alibaba.android.rimet.fdyfn', 'com.alibaba.android.rimet.fosun',
        'com.alibaba.android.rimet.rimm', 'com.alibaba.android.rimet.zj', 'com.alibaba.android.rimet.edu',
        'com.alibaba.taurus', 'com.alibaba.taurus.changchun', 'com.alibaba.taurus.chongqing',
        'com.alibaba.taurus.cpic', 'com.alibaba.taurus.fujian', 'com.alibaba.taurus.hainan',
        'com.alibaba.taurus.hainanxc', 'com.alibaba.taurus.hengdadingems', 'com.alibaba.taurus.jiangxi',
        'com.alibaba.taurus.ningxia', 'com.alibaba.taurus.ningxianew', 'com.alibaba.taurus.qzt',
        'com.alibaba.taurus.xxxs', 'com.alibaba.taurus.zhengzhou', 'com.alibaba.taurus.anhui',
    ],
}

# 去重，构建 (pkg, product_line) 列表
ALL_PKGS = []
seen = set()
for pl, pkgs in CUSTOM_PKGS.items():
    for pkg in pkgs:
        if pkg not in seen:
            ALL_PKGS.append((pkg, pl))
            seen.add(pkg)

# 飞书定制包单独标识
FEISHU_PKGS = set(CUSTOM_PKGS.get('飞书', []))


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def fetch_yingyongbao(client, pkg):
    """从应用宝获取app信息"""
    url = f'https://sj.qq.com/appdetail/{pkg}'
    try:
        r = client.get(url)
        if r.status_code == 404:
            return None, '404'
        if r.status_code != 200:
            return None, f'HTTP_{r.status_code}'
        txt = r.text
        if len(txt) < 2000:
            return None, 'short_page'

        info = {'package_name': pkg, 'url': url, 'source_site': '应用宝'}

        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', txt, re.DOTALL)
        if not m:
            return None, 'no_next_data'

        nd = json.loads(m.group(1))
        pp = nd.get('props', {}).get('pageProps', {})
        dcr = pp.get('dynamicCardResponse', {}).get('data', {})

        if isinstance(dcr, dict):
            for comp in dcr.get('components', []):
                cd = comp.get('data', {})
                if not isinstance(cd, dict):
                    continue
                if cd.get('name') == 'GameDetail':
                    items = cd.get('itemData', [])
                    if isinstance(items, str):
                        items = json.loads(items)
                    if isinstance(items, list) and items:
                        it = items[0]
                        for our_key, their_key in [
                            ('app_name', 'name'), ('developer', 'developer'),
                            ('version', 'version_name'), ('enterprise_name', 'operator'),
                        ]:
                            val = it.get(their_key)
                            if val:
                                info[our_key] = str(val)
                        if it.get('download_num'):
                            info['download_count'] = str(it['download_num'])
                        if it.get('description'):
                            info['description'] = str(it['description'])[:500]
                    break

        # fallback: seoMeta
        seo = pp.get('seoMeta', {})
        if not info.get('app_name') and seo.get('title'):
            title = seo['title']
            n = re.sub(r'\s*[-–—]\s*应用宝.*$', '', title).strip()
            if '-' in n:
                n = n.split('-')[0].strip()
            n = re.sub(r'\s*(app|APP|App|官方|免费|最新|下载|安装).*$', '', n).strip()
            if n and len(n) >= 1 and '应用宝' not in n:
                info['app_name'] = n
        if not info.get('description') and seo.get('description'):
            info['description'] = seo['description'][:500]

        if info.get('app_name'):
            return info, 'ok'
        return None, 'no_app_name'

    except httpx.TimeoutException:
        return None, 'timeout'
    except Exception as e:
        return None, f'exception:{str(e)[:50]}'


def main():
    db = AppInfoDB()
    client = httpx.Client(timeout=20, follow_redirects=True, verify=False, headers=HEADERS)

    # 检查已有的
    existing = set()
    conn = sqlite3.connect('output/results.db')
    c = conn.cursor()
    for row in c.execute('SELECT package_name FROM app_info'):
        existing.add(row[0])
    conn.close()

    total = len(ALL_PKGS)
    ok_count = 0
    fail_404 = []
    fail_other = []
    skipped = []

    print(f"开始爬取 {total} 个定制包名...")
    print(f"数据库已有 {len(existing)} 条记录")
    print()

    for i, (pkg, pl) in enumerate(ALL_PKGS):
        # 跳过已有
        if pkg in existing:
            skipped.append(pkg)
            print(f"[{i+1}/{total}] SKIP {pkg} (已存在)")
            continue

        # 带重试的请求
        info = None
        reason = None
        for attempt in range(3):
            info, reason = fetch_yingyongbao(client, pkg)
            if info is not None or reason == '404':
                break
            if attempt < 2:
                wait = (attempt + 1) * 3 + random.uniform(0, 2)
                print(f"  retry {attempt+1}, wait {wait:.1f}s, reason={reason}")
                time.sleep(wait)

        if info:
            info['product_line'] = pl
            if pkg in FEISHU_PKGS:
                info['discovery_method'] = 'known_feishu_custom'
            elif 'rimet' in pkg:
                info['discovery_method'] = 'known_dingding_custom'
            elif 'taurus' in pkg:
                info['discovery_method'] = 'known_taurus_custom'
            else:
                info['discovery_method'] = 'known_custom_package'

            try:
                ok = db.insert_app(
                    package_name=pkg,
                    app_name=info.get('app_name', ''),
                    product_line=pl,
                    enterprise_name=info.get('enterprise_name', ''),
                    developer=info.get('developer', ''),
                    version=info.get('version', ''),
                    version_code='',
                    update_date='',
                    download_count=info.get('download_count', ''),
                    description=info.get('description', ''),
                    source_site='应用宝',
                    source_url=info.get('url', ''),
                    discovery_method=info.get('discovery_method', 'known_custom_package'),
                )
                if ok:
                    ok_count += 1
                    existing.add(pkg)
                    print(f"[{i+1}/{total}] ✅ {pkg} -> {info.get('app_name', '?')} ({pl})")
                else:
                    print(f"[{i+1}/{total}] ⚠️  {pkg} -> 插入失败(可能重复)")
            except Exception as e:
                print(f"[{i+1}/{total}] ❌ {pkg} -> DB error: {e}")
                fail_other.append((pkg, str(e)[:50]))
        else:
            if reason == '404':
                fail_404.append(pkg)
                print(f"[{i+1}/{total}] ❌ {pkg} -> 应用宝404 (未上架)")
            else:
                fail_other.append((pkg, reason))
                print(f"[{i+1}/{total}] ❌ {pkg} -> {reason}")

        # 请求间隔: 正常0.8-1.5s, 被限流后更长
        if reason in ('timeout', 'short_page') or (reason and 'HTTP_' in str(reason)):
            time.sleep(random.uniform(3, 5))
        else:
            time.sleep(random.uniform(0.8, 1.5))

    # === 汇总报告 ===
    print()
    print("=" * 60)
    print("爬取结果汇总")
    print("=" * 60)
    print(f"总共: {total} 个包名")
    print(f"已存在(跳过): {len(skipped)}")
    print(f"本次成功: {ok_count}")
    print(f"404(未上架): {len(fail_404)}")
    print(f"其他失败: {len(fail_other)}")
    print()

    if fail_404:
        print("--- 404 未上架列表 ---")
        for p in fail_404:
            print(f"  {p}")
    if fail_other:
        print("--- 其他失败列表 ---")
        for p, r in fail_other:
            print(f"  {p} -> {r}")

    # 对成功爬到的执行质量评分和导出
    if ok_count > 0:
        print()
        print("执行质量评分和导出...")
        try:
            from pipeline.quality_scorer import QualityScorer
            from storage.db import CustomerDB
            from storage.exporter import DataExporter
            QualityScorer(db).run()
            cdb = CustomerDB()
            exp = DataExporter(cdb, db)
            for nm, pa in exp.export_all().items():
                print(f"  导出: {nm} -> {pa}")
            exp.print_summary()
            cdb.close()
        except Exception as e:
            print(f"导出失败: {e}")

    db.close()
    client.close()
    print("\n完成!")


if __name__ == '__main__':
    main()
