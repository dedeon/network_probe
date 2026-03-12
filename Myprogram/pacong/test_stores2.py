"""深入测试应用宝和豌豆荚"""
import httpx, json, re
from bs4 import BeautifulSoup

client = httpx.Client(timeout=15, follow_redirects=True, verify=False)
h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

# 1. 应用宝详情页 - 深入解析__NEXT_DATA__
print('=== 应用宝详情页深入解析 ===')
r = client.get('https://sj.qq.com/appdetail/com.tencent.wework', headers=h)
if r.status_code == 200 and '__NEXT_DATA__' in r.text:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
    if m:
        nd = json.loads(m.group(1))
        pp = nd.get('props', {}).get('pageProps', {})
        print(f'pageProps keys: {list(pp.keys())}')
        # 检查dynamicCardResponse
        dcr = pp.get('dynamicCardResponse', {})
        if dcr:
            print(f'dynamicCardResponse keys: {list(dcr.keys())[:10]}')
            cards = dcr.get('cardList', [])
            print(f'cardList count: {len(cards)}')
            for c in cards[:5]:
                print(f"  cardType: {c.get('cardType','')}, title: {c.get('title','')[:30]}")
                items = c.get('cardContent', {}).get('itemList', [])
                for it in items[:2]:
                    print(f"    item: {it.get('appName','')}, pkg: {it.get('pkgName','')}, dev: {it.get('authorName','')}")

# 也试试直接解析HTML
print('\n=== 应用宝详情页 HTML解析 ===')
soup = BeautifulSoup(r.text, 'lxml')
# 查找应用名
title = soup.select_one('title')
print(f'Title: {title.get_text() if title else "N/A"}')
# meta标签
for meta in soup.find_all('meta'):
    name = meta.get('name', '') or meta.get('property', '')
    content = meta.get('content', '')
    if 'description' in name.lower() or 'title' in name.lower():
        print(f'Meta {name}: {content[:100]}')

# 2. 豌豆荚搜索结果深入解析
print('\n=== 豌豆荚搜索结果解析 ===')
for kw in ['企业微信', '钉钉', '飞书', '政务钉钉']:
    r = client.get('https://www.wandoujia.com/search', params={'key': kw}, headers=h)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'lxml')
        # 尝试多种选择器
        items = soup.select('li.card')
        if not items:
            items = soup.select('.search-item')
        if not items:
            items = soup.select('a[href*="/apps/"]')
        print(f'"{kw}": {len(items)} items')
        for it in items[:3]:
            # 找链接
            a = it if it.name == 'a' else it.select_one('a[href*="/apps/"]')
            href = a.get('href', '') if a else ''
            # 提取包名
            pkg = ''
            pm = re.search(r'/apps/([a-zA-Z][a-zA-Z0-9_.]+)', href)
            if pm:
                pkg = pm.group(1)
            name_el = it.select_one('.app-title-h2, .name, h2')
            name = name_el.get_text(strip=True) if name_el else it.get_text(strip=True)[:40]
            dl_el = it.select_one('.install-count')
            dl = dl_el.get_text(strip=True) if dl_el else ''
            print(f'  {name} | pkg={pkg} | dl={dl}')

# 3. 豌豆荚详情页
print('\n=== 豌豆荚详情页 ===')
for pkg in ['com.tencent.wework', 'com.alibaba.android.rimet', 'com.ss.android.lark']:
    r = client.get(f'https://www.wandoujia.com/apps/{pkg}', headers=h)
    print(f'{pkg}: Status={r.status_code}, Len={len(r.text)}')
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'lxml')
        name = soup.select_one('.app-name span, .detail-top h2, title')
        dev = soup.select_one('.dev-sites, .dev-name')
        ver = soup.select_one('.app-version')
        dl = soup.select_one('.install-count, .num-list .item:first-child .num')
        desc = soup.select_one('.desc-info .content, .con')
        print(f'  Name: {name.get_text(strip=True)[:30] if name else "?"}')
        print(f'  Dev: {dev.get_text(strip=True)[:30] if dev else "?"}')
        print(f'  Ver: {ver.get_text(strip=True)[:30] if ver else "?"}')
        print(f'  DL: {dl.get_text(strip=True)[:30] if dl else "?"}')

# 4. 尝试应用宝搜索的替代URL
print('\n=== 应用宝替代搜索URL ===')
for url in [
    'https://sj.qq.com/search?key=企业微信',
    'https://sj.qq.com/myapp/search.htm?kw=企业微信',
]:
    try:
        r = client.get(url, headers=h)
        print(f'{url}: Status={r.status_code}')
        if r.status_code == 200 and '__NEXT_DATA__' in r.text:
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
            if m:
                nd = json.loads(m.group(1))
                pp = nd.get('props', {}).get('pageProps', {})
                print(f'  pageProps keys: {list(pp.keys())[:5]}')
                dcr = pp.get('dynamicCardResponse', {})
                if dcr:
                    cards = dcr.get('cardList', [])
                    for c in cards[:3]:
                        items = c.get('cardContent', {}).get('itemList', [])
                        for it in items[:3]:
                            print(f"    {it.get('appName','')} | {it.get('pkgName','')}")
    except Exception as e:
        print(f'  Error: {e}')

client.close()
print('\nDone!')
