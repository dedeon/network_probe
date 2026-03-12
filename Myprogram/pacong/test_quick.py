"""快速验证各渠道数据提取能力"""
import httpx
import re
import json
from bs4 import BeautifulSoup

client = httpx.Client(timeout=15, follow_redirects=True, verify=False)
UA = {'User-Agent': 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'}

# ========== 测试1: 豌豆荚搜索 ==========
print("=" * 60)
print("测试1: 豌豆荚搜索 '企业微信'")
print("=" * 60)
r = client.get('https://www.wandoujia.com/search', params={'key': '企业微信'}, headers=UA)
print(f"Status: {r.status_code}, Length: {len(r.text)}")
soup = BeautifulSoup(r.text, 'lxml')

# 找所有 /apps/ 链接
app_links = set()
for a in soup.select('a[href*="/apps/"]'):
    href = a.get('href', '')
    m = re.search(r'/apps/(\d+)', href)
    if m:
        app_links.add(('id', m.group(1), a.get_text(strip=True)[:30]))
    else:
        m2 = re.search(r'/apps/([a-zA-Z][a-zA-Z0-9_.]+)', href)
        if m2 and '.' in m2.group(1):
            app_links.add(('pkg', m2.group(1), a.get_text(strip=True)[:30]))

print(f"找到 {len(app_links)} 个应用链接:")
for typ, val, name in list(app_links)[:15]:
    print(f"  [{typ}] {val} - {name}")

# ========== 测试2: 豌豆荚详情页提取包名 ==========
print("\n" + "=" * 60)
print("测试2: 豌豆荚详情页")
print("=" * 60)

# 取几个ID去详情页
test_ids = [item[1] for item in app_links if item[0] == 'id'][:3]
test_pkgs_from_wandoujia = []

for app_id in test_ids:
    url = f'https://www.wandoujia.com/apps/{app_id}'
    r = client.get(url, headers=UA)
    print(f"\n详情页 {url}: Status={r.status_code}")
    if r.status_code == 200:
        text = r.text
        # 提取包名
        pkgs = re.findall(r'\b(com\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9]*)+)\b', text)
        # 过滤掉已知的非包名域名
        domain_kw = ['wandoujia', 'google', 'android.com', 'gstatic', 'googleapis']
        pkgs = [p for p in pkgs if not any(d in p for d in domain_kw)]
        pkgs = list(dict.fromkeys(pkgs))  # 去重保序
        print(f"  找到包名: {pkgs[:5]}")
        
        soup2 = BeautifulSoup(text, 'lxml')
        # 应用名
        name_el = soup2.select_one('.app-name span, .app-name, h1')
        app_name = name_el.get_text(strip=True) if name_el else '?'
        print(f"  应用名: {app_name}")
        
        if pkgs:
            test_pkgs_from_wandoujia.append(pkgs[0])

# ========== 测试3: 应用宝详情页 ==========
print("\n" + "=" * 60)
print("测试3: 应用宝详情页 (已知包名)")
print("=" * 60)

known_pkgs = [
    'com.tencent.wework',
    'com.alibaba.android.rimet',
    'com.ss.android.lark',
    'com.tencent.wecom',
    'com.alibaba.dingtalk.lwsp',
    'com.bytedance.ee.lark',
    'com.tencent.wework.gov',
]

for pkg in known_pkgs:
    url = f'https://sj.qq.com/appdetail/{pkg}'
    try:
        r = client.get(url, headers=UA)
        if r.status_code == 200 and len(r.text) > 1000:
            # 提取title
            soup3 = BeautifulSoup(r.text, 'lxml')
            title = soup3.select_one('title')
            title_text = title.get_text(strip=True) if title else '?'
            # 检查是否是404页面
            if '找不到' in title_text or '404' in title_text or '该应用' in r.text[:500]:
                print(f"  {pkg}: 不存在 (title={title_text[:40]})")
            else:
                print(f"  {pkg}: 存在! title={title_text[:60]}")
        else:
            print(f"  {pkg}: HTTP {r.status_code}")
    except Exception as e:
        print(f"  {pkg}: 错误 {e}")

# ========== 测试4: APKPure搜索 ==========
print("\n" + "=" * 60)
print("测试4: APKPure搜索")
print("=" * 60)

for kw in ['企业微信', '钉钉', '飞书']:
    try:
        r = client.get(f'https://apkpure.com/cn/search?q={kw}', headers=UA)
        print(f"APKPure搜索 '{kw}': Status={r.status_code}, Len={len(r.text)}")
        if r.status_code == 200:
            soup4 = BeautifulSoup(r.text, 'lxml')
            # 找应用列表
            items = soup4.select('a.first-info, a[href*="/cn/"][class*="list"]')
            hrefs = set()
            for a in soup4.select('a[href]'):
                href = a.get('href', '')
                # APKPure格式: /cn/应用名/包名
                m = re.search(r'/cn/[^/]+/(com\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z0-9]+)+)', href)
                if m:
                    hrefs.add(m.group(1))
            print(f"  找到包名: {list(hrefs)[:10]}")
    except Exception as e:
        print(f"  APKPure '{kw}': 错误 {e}")

# ========== 测试5: 豌豆荚更多关键词 ==========
print("\n" + "=" * 60)
print("测试5: 豌豆荚多关键词搜索 (带详情页)")
print("=" * 60)

all_found_apps = []
for kw in ['企业微信', '钉钉', '飞书', '政务钉钉', '浙政钉', '移动OA', '协同办公', 'wework', 'dingtalk', 'lark']:
    r = client.get('https://www.wandoujia.com/search', params={'key': kw}, headers=UA)
    if r.status_code != 200:
        continue
    soup5 = BeautifulSoup(r.text, 'lxml')
    ids = set()
    for a in soup5.select('a[href*="/apps/"]'):
        href = a.get('href', '')
        m = re.search(r'/apps/(\d+)', href)
        if m:
            ids.add(m.group(1))
    
    # 取前5个详情页
    for app_id in list(ids)[:5]:
        url = f'https://www.wandoujia.com/apps/{app_id}'
        try:
            r2 = client.get(url, headers=UA)
            if r2.status_code != 200:
                continue
            pkgs = re.findall(r'\b(com\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9]*)+)\b', r2.text)
            domain_kw = ['wandoujia', 'google', 'android.com', 'gstatic', 'googleapis']
            pkgs = [p for p in pkgs if not any(d in p for d in domain_kw)]
            pkgs = list(dict.fromkeys(pkgs))
            
            soup6 = BeautifulSoup(r2.text, 'lxml')
            name_el = soup6.select_one('.app-name span, .app-name, h1')
            app_name = name_el.get_text(strip=True) if name_el else '?'
            
            if pkgs:
                all_found_apps.append({
                    'pkg': pkgs[0],
                    'name': app_name,
                    'keyword': kw,
                    'source': 'wandoujia'
                })
        except:
            pass

print(f"\n总共从豌豆荚发现 {len(all_found_apps)} 个应用:")
seen = set()
for app in all_found_apps:
    if app['pkg'] not in seen:
        seen.add(app['pkg'])
        print(f"  {app['pkg']:45s} | {app['name']:20s} | kw={app['keyword']}")

print(f"\n去重后唯一包名: {len(seen)}")

client.close()
