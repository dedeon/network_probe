"""测试各应用商店API可用性"""
import httpx
import json
from bs4 import BeautifulSoup

client = httpx.Client(timeout=15, follow_redirects=True, verify=False)
h = {'User-Agent': 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'}

kw = '企业微信'

# 1. 华为
print('=== 华为AppGallery ===')
try:
    r = client.get('https://web-drcn.hispace.dbankcloud.cn/uowap/index', params={
        'method': 'internal.getTabDetail', 'serviceType': 20, 'reqPageNum': 1,
        'maxResults': 5, 'uri': f'searchword|{kw}', 'keyword': kw, 'zone': '', 'locale': 'zh'}, headers=h)
    print(f'Status: {r.status_code}, Len: {len(r.text)}')
    if r.status_code == 200:
        data = r.json()
        print(f'Keys: {list(data.keys())[:5]}')
        ld = data.get('layoutData', [])
        for l in ld[:2]:
            dl = l.get('dataList', [])
            for d in dl[:3]:
                print(f"  App: {d.get('name','')} | {d.get('package','')} | {d.get('packageName','')}")
except Exception as e:
    print(f'Error: {e}')

# 2. 小米
print('\n=== 小米 ===')
try:
    r = client.get('https://app.mi.com/searchAll', params={'keywords': kw}, headers=h)
    print(f'Status: {r.status_code}, Len: {len(r.text)}')
    if r.status_code == 200 and len(r.text) > 100:
        soup = BeautifulSoup(r.text, 'lxml')
        items = soup.select('.applist-app, .app-list li, a[href*="/details?id="]')
        print(f'Items: {len(items)}')
        for it in items[:3]:
            print(f'  Item: {it.get_text(strip=True)[:60]}')
except Exception as e:
    print(f'Error: {e}')

# 3. 应用宝
print('\n=== 应用宝 ===')
for url, name in [
    ('https://sj.qq.com/appdetail/com.tencent.wework', 'detail_page'),
    ('https://sj.qq.com/search?key=企业微信', 'search_page'),
]:
    try:
        r = client.get(url, headers=h)
        print(f'{name}: Status={r.status_code}, Len={len(r.text)}')
        if r.status_code == 200:
            has_ww = 'com.tencent.wework' in r.text or 'wework' in r.text.lower()
            print(f'  Has wework: {has_ww}')
            # Try to find __NEXT_DATA__ or similar
            if '__NEXT_DATA__' in r.text:
                import re
                m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
                if m:
                    nd = json.loads(m.group(1))
                    print(f'  __NEXT_DATA__ keys: {list(nd.get("props",{}).get("pageProps",{}).keys())[:5]}')
    except Exception as e:
        print(f'{name} Error: {e}')

# 4. 豌豆荚
print('\n=== 豌豆荚 ===')
try:
    r = client.get('https://www.wandoujia.com/search', params={'key': kw}, headers=h)
    print(f'Status: {r.status_code}, Len: {len(r.text)}')
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'lxml')
        items = soup.select('.search-item, .app-desc-wrap, li.card, a[href*="/apps/"]')
        print(f'Items: {len(items)}')
        for it in items[:3]:
            href = it.get('href', '') if it.name == 'a' else (it.select_one('a[href*="/apps/"]') or {}).get('href', '')
            text = it.get_text(strip=True)[:60]
            print(f'  {text} -> {href}')
except Exception as e:
    print(f'Error: {e}')

# 5. OPPO
print('\n=== OPPO ===')
try:
    r = client.get('https://store.oppomobile.com/api/market/search', params={'q': kw, 'pageNo': 1, 'pageSize': 5}, headers=h)
    print(f'Status: {r.status_code}, Len: {len(r.text)}')
    if r.status_code == 200:
        try:
            data = r.json()
            print(f'Keys: {list(data.keys())[:5]}')
        except:
            print(f'Not JSON: {r.text[:200]}')
except Exception as e:
    print(f'Error: {e}')

# 6. vivo
print('\n=== vivo ===')
try:
    r = client.get('https://h5-appstore-api.vivo.com.cn/search', params={'keyword': kw, 'pageIndex': 1, 'pageSize': 5}, headers=h)
    print(f'Status: {r.status_code}, Len: {len(r.text)}')
    if r.status_code == 200:
        try:
            data = r.json()
            print(f'Keys: {list(data.keys())[:5]}')
        except:
            print(f'Not JSON: {r.text[:200]}')
except Exception as e:
    print(f'Error: {e}')

# 7. 直接用应用宝详情API获取已知包信息
print('\n=== 应用宝 appdetail API ===')
known_pkgs = ['com.tencent.wework', 'com.alibaba.android.rimet', 'com.ss.android.lark']
for pkg in known_pkgs:
    try:
        r = client.get(f'https://sj.qq.com/appdetail/{pkg}', headers=h)
        print(f'{pkg}: Status={r.status_code}, Len={len(r.text)}')
        if r.status_code == 200 and '__NEXT_DATA__' in r.text:
            import re
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
            if m:
                nd = json.loads(m.group(1))
                pp = nd.get('props', {}).get('pageProps', {})
                ad = pp.get('appDetail', pp.get('data', {}))
                if isinstance(ad, dict):
                    print(f'  Name: {ad.get("appName","")}, Pkg: {ad.get("pkgName","")}, Dev: {ad.get("authorName","")}')
    except Exception as e:
        print(f'{pkg} Error: {e}')

client.close()
print('\nDone!')
