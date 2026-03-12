"""深入测试豌豆荚详情页和应用宝详情页数据结构"""
import httpx, json, re
from bs4 import BeautifulSoup

client = httpx.Client(timeout=15, follow_redirects=True, verify=False)
h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

# 1. 豌豆荚详情页 - 完整数据提取
print('=== 豌豆荚详情页完整 ===')
r = client.get('https://www.wandoujia.com/apps/com.tencent.wework', headers=h)
if r.status_code == 200:
    soup = BeautifulSoup(r.text, 'lxml')
    # 所有meta标签
    for meta in soup.find_all('meta'):
        name = meta.get('name','') or meta.get('property','')
        content = meta.get('content','')
        if content and len(content) > 3:
            print(f'  meta[{name}]: {content[:80]}')
    
    # 查找应用信息区域
    print('\n--- 详情信息 ---')
    # 尝试各种选择器
    for sel in ['.app-name', '.detail-top', '.app-info', '.app-tags', '.head-content',
                '.head-info', '.app-title', '.apk-info', 'h1', '.download-wp']:
        el = soup.select_one(sel)
        if el:
            print(f'  {sel}: {el.get_text(strip=True)[:80]}')
    
    # 查找版本、大小等信息
    print('\n--- 详细信息元素 ---')
    for el in soup.select('.infos-list li, .info-list li, .app-info-item, .apk-info-item, dl dd, .detail-info span'):
        text = el.get_text(strip=True)
        if text and len(text) < 100:
            print(f'  item: {text}')
    
    # 检查下载量
    for el in soup.select('.install-count, .num-list .item, .download-num, .num'):
        print(f'  download: {el.get_text(strip=True)[:60]}')
    
    # 开发者
    for el in soup.select('.dev-sites a, .developer a, .dev-name, a[href*="developer"]'):
        print(f'  dev: {el.get_text(strip=True)[:60]} -> {el.get("href","")}')

# 2. 豌豆荚搜索 - 尝试提取包名
print('\n=== 豌豆荚搜索 - 提取包名 ===')
r = client.get('https://www.wandoujia.com/search', params={'key': '企业微信'}, headers=h)
if r.status_code == 200:
    soup = BeautifulSoup(r.text, 'lxml')
    # 更详细地查看搜索结果结构
    cards = soup.select('li.card')
    for card in cards[:5]:
        a = card.select_one('a')
        href = a.get('href', '') if a else ''
        name_el = card.select_one('.name, h2, .title')
        name = name_el.get_text(strip=True) if name_el else ''
        # 尝试从链接提取包名
        pkg = ''
        pm = re.search(r'/apps/(\d+|[a-zA-Z][a-zA-Z0-9_.]+)', href)
        if pm:
            pkg = pm.group(1)
        # 检查data属性
        data_attrs = {k:v for k,v in card.attrs.items() if k.startswith('data')}
        print(f'  name={name[:30]}, href={href[:60]}, pkg={pkg}, data={data_attrs}')
        # 显示card的HTML结构
        print(f'    HTML: {str(card)[:200]}')

# 3. 应用宝详情页 - 完整数据提取  
print('\n=== 应用宝详情页 ===')
r = client.get('https://sj.qq.com/appdetail/com.tencent.wework', headers=h)
if r.status_code == 200:
    soup = BeautifulSoup(r.text, 'lxml')
    # 查找所有有数据的元素
    for sel in ['.app-info', '.det-name', '.det-ins', '.det-othinfo', 
                '.det-app-data', 'h1', '.detail-hd']:
        el = soup.select_one(sel)
        if el:
            print(f'  {sel}: {el.get_text(strip=True)[:80]}')
    
    # 检查是否有JSON数据嵌入
    for script in soup.find_all('script'):
        text = script.string or ''
        if 'appName' in text or 'pkgName' in text or 'wework' in text:
            print(f'\n  Found script with app data, len={len(text)}')
            print(f'  First 300: {text[:300]}')
            break
    
    # __NEXT_DATA__ 深入
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
    if m:
        nd = json.loads(m.group(1))
        pp = nd.get('props', {}).get('pageProps', {})
        dcr = pp.get('dynamicCardResponse', {})
        data = dcr.get('data', {})
        if isinstance(data, dict):
            print(f'\n  data keys: {list(data.keys())[:20]}')
            for k, v in data.items():
                if isinstance(v, (str, int, float)):
                    print(f'    {k}: {str(v)[:100]}')
                elif isinstance(v, dict):
                    print(f'    {k}: dict with keys {list(v.keys())[:5]}')
                elif isinstance(v, list):
                    print(f'    {k}: list of {len(v)} items')

client.close()
print('\nDone!')
