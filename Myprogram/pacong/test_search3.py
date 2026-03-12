#!/usr/bin/env python3
"""用引号包裹包名进行精确搜索测试"""
import httpx
import re
import time
import urllib.parse

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

client = httpx.Client(timeout=20, follow_redirects=True, verify=False, headers=HEADERS)

test_pkgs = [
    'com.ss.android.lark.greentown',
    'com.alibaba.android.rimet.fosun',
    'com.alibaba.taurus.fujian',
    'com.ss.android.lark.ihaier',
    'com.ss.android.lark.mdzh',
]

def parse_bing(html):
    """解析Bing搜索结果"""
    results = []
    algos = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)
    for algo in algos[:8]:
        title_m = re.search(r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', algo, re.DOTALL)
        if title_m:
            link = title_m.group(1)
            title = re.sub(r'<[^>]+>', '', title_m.group(2)).strip()
            # 解码bing的跳转链接
            real_link_m = re.search(r'u=a1(.*?)&', link)
            if real_link_m:
                import base64
                try:
                    real_link = base64.b64decode(real_link_m.group(1) + '==').decode('utf-8', errors='ignore')
                    link = real_link
                except:
                    pass
            desc_m = re.search(r'<p[^>]*>(.*?)</p>', algo, re.DOTALL)
            desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip() if desc_m else ''
            results.append({'title': title, 'link': link, 'desc': desc})
    return results

def parse_sogou(html):
    """解析搜狗搜索结果"""
    results = []
    # 搜狗结果在 <div class="vrwrap"> 或 <div class="rb">
    blocks = re.findall(r'<h3[^>]*>(.*?)</h3>.*?(?:<p[^>]*class="[^"]*str[^"]*"[^>]*>(.*?)</p>)?', html, re.DOTALL)
    for title_html, desc_html in blocks[:8]:
        link_m = re.search(r'href="(https?://[^"]+)"', title_html)
        title = re.sub(r'<[^>]+>', '', title_html).strip()
        desc = re.sub(r'<[^>]+>', '', desc_html).strip() if desc_html else ''
        link = link_m.group(1) if link_m else ''
        if title:
            results.append({'title': title, 'link': link, 'desc': desc})
    return results

def parse_google(html):
    """解析Google搜索结果"""
    results = []
    # Google结果在 <div class="g"> 中
    blocks = re.findall(r'<div class="[^"]*g[^"]*">(.*?)</div>\s*</div>\s*</div>', html, re.DOTALL)
    for block in blocks[:8]:
        title_m = re.search(r'<h3[^>]*>(.*?)</h3>', block, re.DOTALL)
        link_m = re.search(r'<a href="(https?://[^"]+)"', block)
        desc_m = re.search(r'<span[^>]*>(.*?)</span>', block, re.DOTALL)
        if title_m:
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
            link = link_m.group(1) if link_m else ''
            desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip() if desc_m else ''
            results.append({'title': title, 'link': link, 'desc': desc})
    return results

for pkg in test_pkgs:
    print(f"\n{'='*70}")
    print(f"搜索: {pkg}")
    print(f"{'='*70}")
    
    # Bing - 用引号精确搜索
    try:
        query = urllib.parse.quote(f'"{pkg}"')
        r = client.get(f'https://www.bing.com/search?q={query}', timeout=15)
        results = parse_bing(r.text)
        print(f"\n  Bing ({len(results)}个结果):")
        for i, res in enumerate(results[:5]):
            print(f"    [{i+1}] {res['title']}")
            print(f"        {res['link'][:80]}")
            if res['desc']:
                print(f"        {res['desc'][:120]}")
    except Exception as e:
        print(f"  Bing失败: {e}")
    
    time.sleep(1)
    
    # 搜狗 - 用引号精确搜索 
    try:
        query = urllib.parse.quote(f'"{pkg}"')
        r = client.get(f'https://www.sogou.com/web?query={query}', timeout=15)
        results = parse_sogou(r.text)
        print(f"\n  搜狗 ({len(results)}个结果):")
        for i, res in enumerate(results[:5]):
            print(f"    [{i+1}] {res['title']}")
            if res['link']:
                print(f"        {res['link'][:80]}")
            if res['desc']:
                print(f"        {res['desc'][:120]}")
    except Exception as e:
        print(f"  搜狗失败: {e}")
    
    time.sleep(1)

    # Google
    try:
        query = urllib.parse.quote(f'"{pkg}"')
        r = client.get(f'https://www.google.com/search?q={query}', timeout=15)
        results = parse_google(r.text)
        print(f"\n  Google ({len(results)}个结果):")
        for i, res in enumerate(results[:5]):
            print(f"    [{i+1}] {res['title']}")
            if res['link']:
                print(f"        {res['link'][:80]}")
    except Exception as e:
        print(f"  Google失败: {e}")
    
    time.sleep(1)

client.close()
print("\n\n测试完成!")
