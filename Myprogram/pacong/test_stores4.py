"""提取应用宝NEXT_DATA和豌豆荚m版搜索"""
import httpx, json, re
from bs4 import BeautifulSoup

client = httpx.Client(timeout=15, follow_redirects=True, verify=False)
h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# 1. 应用宝 - 从__NEXT_DATA__提取完整数据
print('=== 应用宝 __NEXT_DATA__ 完整数据 ===')
r = client.get('https://sj.qq.com/appdetail/com.tencent.wework', headers=h)
if r.status_code == 200:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
    if m:
        nd = json.loads(m.group(1))
        pp = nd.get('props', {}).get('pageProps', {})
        dcr = pp.get('dynamicCardResponse', {})
        data = dcr.get('data', {})
        if data:
            # 递归打印所有非空字符串值
            def print_dict(d, prefix=''):
                if isinstance(d, dict):
                    for k, v in d.items():
                        if isinstance(v, (str, int, float)) and v:
                            print(f'{prefix}{k}: {str(v)[:100]}')
                        elif isinstance(v, dict):
                            print_dict(v, prefix + k + '.')
                        elif isinstance(v, list) and len(v) > 0:
                            print(f'{prefix}{k}: list[{len(v)}]')
                            if len(v) > 0 and isinstance(v[0], dict):
                                print_dict(v[0], prefix + k + '[0].')
            print_dict(data)
        else:
            # Try context
            ctx = pp.get('context', {})
            print_dict = None
            ii = ctx.get('initialInfo', {})
            sd = ctx.get('serverData', {})
            print(f'initialInfo keys: {list(ii.keys())[:10]}')
            print(f'serverData keys: {list(sd.keys()) if isinstance(sd, dict) else type(sd)}')
            
            # Also check seoMeta
            seo = pp.get('seoMeta', {})
            print(f'\nseoMeta: {json.dumps(seo, ensure_ascii=False)[:500]}')

# 2. 豌豆荚移动版搜索
print('\n\n=== 豌豆荚移动版搜索 ===')
mh = {'User-Agent': 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'}
for kw in ['企业微信', '钉钉']:
    r = client.get(f'https://m.wandoujia.com/search', params={'key': kw}, headers=mh)
    print(f'\n"{kw}": Status={r.status_code}, Len={len(r.text)}')
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'lxml')
        items = soup.select('.app-card, .search-item, .app-item, li.card, a[href*="/apps/"]')
        print(f'Items: {len(items)}')
        for it in items[:5]:
            a = it if it.name == 'a' else it.select_one('a')
            href = a.get('href', '') if a else ''
            text = it.get_text(strip=True)[:60]
            pkg_match = re.search(r'/apps/(\d+|[a-zA-Z][a-zA-Z0-9_.]+)', href)
            pkg = pkg_match.group(1) if pkg_match else ''
            print(f'  text={text}, href={href[:60]}, pkg_or_id={pkg}')

# 3. 豌豆荚详情页 - 尝试用数字ID
print('\n\n=== 豌豆荚详情页(数字ID) ===')
for url in ['https://www.wandoujia.com/apps/6860656', 'https://m.wandoujia.com/apps/6860656']:
    r = client.get(url, headers=h)
    print(f'{url}: Status={r.status_code}')
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'lxml')
        name = soup.select_one('.app-name, .detail-app-title, title')
        print(f'  Name: {name.get_text(strip=True)[:50] if name else "?"}')
        # 查找包名
        text = soup.get_text()
        pkg_m = re.search(r'com\.[a-zA-Z][a-zA-Z0-9_.]+', text)
        if pkg_m:
            print(f'  Package found: {pkg_m.group()}')

# 4. 应用宝搜索-遍历
print('\n\n=== 应用宝category ===')
r = client.get('https://sj.qq.com/myapp/category.htm?orgame=1', headers=h)
print(f'Status: {r.status_code}')
if r.status_code == 200 and '__NEXT_DATA__' in r.text:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
    if m:
        nd = json.loads(m.group(1))
        pp = nd.get('props', {}).get('pageProps', {})
        dcr = pp.get('dynamicCardResponse', {})
        cards = dcr.get('cardList', dcr.get('data', {}).get('cardList', []) if isinstance(dcr.get('data'), dict) else [])
        print(f'Cards: {len(cards) if isinstance(cards, list) else type(cards)}')

client.close()
print('\nDone!')
