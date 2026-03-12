#!/usr/bin/env python3
"""测试搜索引擎搜索包名的效果"""
import httpx
import re

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
    'com.alibaba.android.rimet.czd',
]

for pkg in test_pkgs:
    print(f"\n{'='*60}")
    print(f"搜索: {pkg}")
    print(f"{'='*60}")
    
    # bing搜索
    try:
        r = client.get(f'https://cn.bing.com/search?q={pkg}', timeout=15)
        print(f"Bing状态码: {r.status_code}, 长度: {len(r.text)}")
        
        results = re.findall(r'<li class="b_algo">(.*?)</li>', r.text, re.DOTALL)
        print(f"搜索结果数: {len(results)}")
        
        for i, res in enumerate(results[:5]):
            title_m = re.search(r'<h2>(.*?)</h2>', res, re.DOTALL)
            link_m = re.search(r'href="(https?://[^"]+)"', res)
            desc_m = re.search(r'<p[^>]*>(.*?)</p>', res, re.DOTALL)
            title = re.sub(r'<.*?>', '', title_m.group(1)).strip() if title_m else 'N/A'
            link = link_m.group(1) if link_m else 'N/A'
            desc = re.sub(r'<.*?>', '', desc_m.group(1)).strip() if desc_m else 'N/A'
            print(f"\n  [{i+1}] {title}")
            print(f"      链接: {link}")
            print(f"      摘要: {desc[:120]}")
    except Exception as e:
        print(f"Bing搜索失败: {e}")
    
    # 也试试百度搜索
    try:
        r2 = client.get(f'https://www.baidu.com/s?wd={pkg}', timeout=15)
        print(f"\n  百度状态码: {r2.status_code}, 长度: {len(r2.text)}")
        # 百度搜索结果
        results2 = re.findall(r'<div class="result c-container[^"]*"(.*?)</div>\s*</div>', r2.text, re.DOTALL)
        if not results2:
            results2 = re.findall(r'<h3 class="[^"]*">(.*?)</h3>', r2.text, re.DOTALL)
        print(f"  百度结果数: {len(results2)}")
        for i, res in enumerate(results2[:3]):
            title_text = re.sub(r'<.*?>', '', res).strip()
            print(f"  百度[{i+1}]: {title_text[:100]}")
    except Exception as e:
        print(f"  百度搜索失败: {e}")

    import time
    time.sleep(1)

client.close()
print("\n\n测试完成!")
