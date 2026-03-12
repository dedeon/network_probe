#!/usr/bin/env python3
"""诊断缺失的68个定制包在各应用商店上的可用性"""
import httpx
import re
import json
import time
import random

MISSING = [
    # 飞书定制
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
    # 钉钉定制
    'com.alibaba.android.rimet.adt', 'com.alibaba.android.rimet.aliding',
    'com.alibaba.android.rimet.bgyfw', 'com.alibaba.android.rimet.bitding', 'com.alibaba.android.rimet.catlcome',
    'com.alibaba.android.rimet.ccflink', 'com.alibaba.android.rimet.czd', 'com.alibaba.android.rimet.diswu',
    'com.alibaba.android.rimet.faw_easy', 'com.alibaba.android.rimet.fdyfn', 'com.alibaba.android.rimet.fosun',
    'com.alibaba.android.rimet.rimm', 'com.alibaba.android.rimet.zj', 'com.alibaba.android.rimet.edu',
    # 浙政钉/taurus
    'com.alibaba.taurus', 'com.alibaba.taurus.changchun', 'com.alibaba.taurus.chongqing',
    'com.alibaba.taurus.cpic', 'com.alibaba.taurus.fujian', 'com.alibaba.taurus.hainan',
    'com.alibaba.taurus.hainanxc', 'com.alibaba.taurus.hengdadingems', 'com.alibaba.taurus.jiangxi',
    'com.alibaba.taurus.ningxia', 'com.alibaba.taurus.ningxianew', 'com.alibaba.taurus.qzt',
    'com.alibaba.taurus.xxxs', 'com.alibaba.taurus.zhengzhou', 'com.alibaba.taurus.anhui',
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

cl = httpx.Client(timeout=15, follow_redirects=True, verify=False, headers=HEADERS)

# --- 测试应用宝 ---
print("=" * 60)
print("测试1: 应用宝 (sj.qq.com)")
print("=" * 60)
yingyongbao_ok = []
yingyongbao_404 = []
yingyongbao_err = []

sample = MISSING[:10]  # 先测10个
for pkg in sample:
    try:
        url = f'https://sj.qq.com/appdetail/{pkg}'
        r = cl.get(url)
        if r.status_code != 200:
            yingyongbao_err.append((pkg, f'HTTP {r.status_code}'))
            print(f"  HTTP_ERR {pkg} -> {r.status_code}")
            continue
        if len(r.text) < 2000:
            yingyongbao_404.append(pkg)
            print(f"  SHORT    {pkg} -> {len(r.text)} bytes")
            continue
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
        if not m:
            yingyongbao_404.append(pkg)
            print(f"  NO_NEXT  {pkg}")
            continue
        nd = json.loads(m.group(1))
        pp = nd.get('props', {}).get('pageProps', {})
        dcr = pp.get('dynamicCardResponse', {}).get('data', {})
        found = False
        if isinstance(dcr, dict):
            for comp in dcr.get('components', []):
                cd = comp.get('data', {})
                if isinstance(cd, dict) and cd.get('name') == 'GameDetail':
                    items = cd.get('itemData', [])
                    if isinstance(items, str):
                        items = json.loads(items)
                    if items:
                        it = items[0]
                        print(f"  OK       {pkg} -> {it.get('name', '?')}")
                        yingyongbao_ok.append(pkg)
                        found = True
                    break
        if not found:
            yingyongbao_404.append(pkg)
            print(f"  NO_DATA  {pkg}")
    except Exception as e:
        yingyongbao_err.append((pkg, str(e)[:60]))
        print(f"  EXC      {pkg} -> {e}")
    time.sleep(0.5)

print(f"\n应用宝结果 (样本10个): OK={len(yingyongbao_ok)} 404={len(yingyongbao_404)} ERR={len(yingyongbao_err)}")

# --- 测试豌豆荚 ---
print("\n" + "=" * 60)
print("测试2: 豌豆荚 (www.wandoujia.com)")
print("=" * 60)
wandoujia_ok = []
wandoujia_404 = []
for pkg in sample:
    try:
        url = f'https://www.wandoujia.com/apps/{pkg}'
        r = cl.get(url)
        if r.status_code == 200 and len(r.text) > 5000:
            # 提取app名称
            m = re.search(r'<span class="title">(.*?)</span>', r.text)
            name = m.group(1) if m else '?'
            print(f"  OK       {pkg} -> {name}")
            wandoujia_ok.append(pkg)
        else:
            wandoujia_404.append(pkg)
            print(f"  404      {pkg} -> status={r.status_code} len={len(r.text)}")
    except Exception as e:
        wandoujia_404.append(pkg)
        print(f"  EXC      {pkg} -> {e}")
    time.sleep(0.5)

print(f"\n豌豆荚结果 (样本10个): OK={len(wandoujia_ok)} 404={len(wandoujia_404)}")

# --- 测试酷安 ---
print("\n" + "=" * 60)
print("测试3: 酷安 (www.coolapk.com)")
print("=" * 60)
coolapk_ok = []
coolapk_404 = []
for pkg in sample[:5]:  # 酷安限制更严，先测5个
    try:
        url = f'https://www.coolapk.com/apk/{pkg}'
        r = cl.get(url)
        if r.status_code == 200 and len(r.text) > 5000:
            m = re.search(r'<p class="detail_app_title">(.*?)</p>', r.text)
            name = m.group(1).strip() if m else '?'
            print(f"  OK       {pkg} -> {name}")
            coolapk_ok.append(pkg)
        else:
            coolapk_404.append(pkg)
            print(f"  404      {pkg} -> status={r.status_code} len={len(r.text)}")
    except Exception as e:
        coolapk_404.append(pkg)
        print(f"  EXC      {pkg} -> {e}")
    time.sleep(1)

print(f"\n酷安结果 (样本5个): OK={len(coolapk_ok)} 404={len(coolapk_404)}")

# --- 测试华为应用市场 ---
print("\n" + "=" * 60)
print("测试4: 华为应用市场 (appgallery.huawei.com)")
print("=" * 60)
huawei_ok = []
huawei_404 = []
for pkg in sample[:5]:
    try:
        url = f'https://appgallery.huawei.com/app/{pkg}'
        r = cl.get(url)
        if r.status_code == 200 and len(r.text) > 3000:
            print(f"  OK       {pkg} -> len={len(r.text)}")
            huawei_ok.append(pkg)
        else:
            huawei_404.append(pkg)
            print(f"  404      {pkg} -> status={r.status_code} len={len(r.text)}")
    except Exception as e:
        huawei_404.append(pkg)
        print(f"  EXC      {pkg} -> {e}")
    time.sleep(1)

print(f"\n华为结果 (样本5个): OK={len(huawei_ok)} 404={len(huawei_404)}")

# --- 总结 ---
print("\n" + "=" * 60)
print("总结")
print("=" * 60)
print(f"应用宝: {len(yingyongbao_ok)}/10")
print(f"豌豆荚: {len(wandoujia_ok)}/10")
print(f"酷安:   {len(coolapk_ok)}/5")
print(f"华为:   {len(huawei_ok)}/5")
print(f"\n推荐: 优先使用成功率最高的应用商店")

cl.close()
