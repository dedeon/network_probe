#!/usr/bin/env python3
"""深入分析应用宝HTML结构"""
import httpx, re, json

c = httpx.Client(timeout=20, follow_redirects=True, verify=False,
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})

# 测试一个失败的包名
for pkg in ['cn.wps.moffice_eng', 'com.tencent.mobileqq']:
    print(f"\n{'='*60}")
    print(f"包名: {pkg}")
    r = c.get(f'https://sj.qq.com/appdetail/{pkg}')
    
    # 检查__NEXT_DATA__详细结构
    nd = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
    if nd:
        data = json.loads(nd.group(1))
        pp = data.get('props', {}).get('pageProps', {})
        
        # 打印所有顶级key
        print(f"  pageProps keys: {list(pp.keys())}")
        
        dcr = pp.get('dynamicCardResponse', {})
        if dcr:
            d = dcr.get('data', {})
            print(f"  dynamicCardResponse.data type: {type(d)}")
            if isinstance(d, dict):
                print(f"  data keys: {list(d.keys())}")
                comps = d.get('components', [])
                print(f"  components count: {len(comps)}")
                for i, comp in enumerate(comps):
                    cd = comp.get('data', {})
                    if isinstance(cd, dict):
                        # 打印所有有值的key
                        non_empty = {k: str(v)[:50] for k, v in cd.items() if v and k not in ['description']}
                        if non_empty:
                            print(f"    comp[{i}]: {non_empty}")
        
        # 也检查其他可能的数据路径
        for key in pp:
            if key != 'dynamicCardResponse' and pp[key]:
                val = pp[key]
                if isinstance(val, dict):
                    print(f"  pageProps[{key}] (dict): keys={list(val.keys())[:5]}")
                elif isinstance(val, str) and len(val) > 0:
                    print(f"  pageProps[{key}] (str): {val[:80]}")
                else:
                    print(f"  pageProps[{key}]: {type(val)}")
    else:
        print("  __NEXT_DATA__ NOT FOUND!")
        # 搜索其他可能的JSON数据
        for m in re.finditer(r'<script[^>]*>(.*?)</script>', r.text[:50000], re.DOTALL):
            s = m.group(1)
            if 'appName' in s or 'pkgName' in s or 'packageName' in s:
                print(f"  Found script with app data: {s[:200]}")

c.close()
