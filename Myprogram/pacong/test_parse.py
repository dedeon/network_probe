#!/usr/bin/env python3
"""测试应用宝详情页HTML解析"""
import httpx, re, json

c = httpx.Client(timeout=20, follow_redirects=True, verify=False,
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})

test_pkgs = [
    'cn.wps.moffice_eng',   # WPS
    'com.tencent.mobileqq', # QQ
    'cmb.pb',               # 招商银行
    'com.chinamworld.main',  # 建设银行
    'com.android.bankabc',   # 农行
    'com.tencent.wework',    # 企业微信（已成功的）
]

for pkg in test_pkgs:
    print(f"\n{'='*60}")
    print(f"测试包名: {pkg}")
    r = c.get(f'https://sj.qq.com/appdetail/{pkg}')
    print(f"  status={r.status_code}, len={len(r.text)}")
    
    # title tag
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, 'lxml')
    title = soup.select_one('title')
    if title:
        print(f"  title tag: {title.get_text(strip=True)[:80]}")
    else:
        print(f"  title tag: NOT FOUND")
    
    # Check if it's a 404 page
    if '找不到' in r.text[:5000]:
        print(f"  => 404页面")
        continue
    
    # meta description
    for meta in soup.find_all('meta'):
        name = meta.get('name', '') or meta.get('property', '')
        if 'description' in name.lower():
            print(f"  meta description: {meta.get('content', '')[:80]}")
            break
    
    # __NEXT_DATA__
    nd = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
    if nd:
        try:
            data = json.loads(nd.group(1))
            pp = data.get('props', {}).get('pageProps', {})
            dcr = pp.get('dynamicCardResponse', {})
            d = dcr.get('data', {})
            if isinstance(d, dict):
                comps = d.get('components', [])
                print(f"  __NEXT_DATA__ components: {len(comps)}")
                for comp in comps[:5]:
                    cd = comp.get('data', {})
                    if isinstance(cd, dict):
                        keys_found = {k: cd[k] for k in ['appName', 'authorName', 'versionName', 'pkgName', 'appDownCount'] if cd.get(k)}
                        if keys_found:
                            print(f"    => {keys_found}")
            else:
                print(f"  __NEXT_DATA__ data type: {type(d)}")
        except Exception as e:
            print(f"  __NEXT_DATA__ parse error: {e}")
    else:
        print(f"  __NEXT_DATA__: NOT FOUND")
        # Check what's in the HTML
        scripts = soup.find_all('script', id=True)
        print(f"  scripts with id: {[s.get('id') for s in scripts]}")

c.close()
print("\n\n=== 完成 ===")
