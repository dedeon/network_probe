#!/usr/bin/env python3
"""分析itemData中的实际数据结构"""
import httpx, re, json

c = httpx.Client(timeout=20, follow_redirects=True, verify=False,
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

for pkg in ['cn.wps.moffice_eng', 'com.tencent.wework']:
    print(f"\n{'='*60}")
    print(f"包名: {pkg}")
    r = c.get(f'https://sj.qq.com/appdetail/{pkg}')
    
    nd = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
    if nd:
        data = json.loads(nd.group(1))
        pp = data.get('props', {}).get('pageProps', {})
        
        # 检查seoMeta
        seo = pp.get('seoMeta', {})
        print(f"  seoMeta title: {seo.get('title', 'N/A')[:60]}")
        print(f"  seoMeta desc: {seo.get('description', 'N/A')[:60]}")
        
        dcr = pp.get('dynamicCardResponse', {})
        d = dcr.get('data', {})
        comps = d.get('components', [])
        
        # 找GameDetail组件
        for comp in comps:
            if comp.get('data', {}).get('name') == 'GameDetail':
                cd = comp['data']
                item_data = cd.get('itemData', [])
                if item_data:
                    items = json.loads(item_data) if isinstance(item_data, str) else item_data
                    for item in items[:1]:
                        print(f"\n  itemData keys: {list(item.keys())}")
                        # 打印所有有值的关键字段
                        for k in sorted(item.keys()):
                            v = item[k]
                            if v and k not in ['icon_url', 'apk_url', 'apk_md5', 'icon_urls', 'screenshot_url', 'video_url', 'certificate_url']:
                                print(f"    {k}: {str(v)[:80]}")
        
        # 也提取推荐列表中的包名
        related_pkgs = []
        for comp in comps:
            cd = comp.get('data', {})
            if cd.get('name') in ['YouMayAlsoLike', 'SameDeveloper']:
                item_data = cd.get('itemData', [])
                if item_data:
                    items = json.loads(item_data) if isinstance(item_data, str) else item_data
                    for item in items:
                        if item.get('pkg_name'):
                            related_pkgs.append((item['pkg_name'], item.get('app_name', '')))
        
        if related_pkgs:
            print(f"\n  相关推荐 ({len(related_pkgs)} apps):")
            for p, n in related_pkgs[:10]:
                print(f"    {p}: {n}")

c.close()
