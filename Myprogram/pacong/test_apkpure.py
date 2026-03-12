"""深入测试APKPure作为主搜索源的能力"""
import httpx
import re
import json
import time
from bs4 import BeautifulSoup

client = httpx.Client(timeout=20, follow_redirects=True, verify=False)
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

all_apps = {}  # pkg -> {name, developer, kw, url}

# 搜索关键词列表 - 覆盖三大产品线及其定制版
keywords = [
    # 企业微信系列
    '企业微信', 'wework', 'wecom', '政务微信', '企业微信定制',
    # 钉钉系列  
    '钉钉', 'dingtalk', '政务钉钉', '浙政钉', '钉钉专属',
    '钉钉定制', '粤政易', '赣政通',
    # 飞书系列
    '飞书', 'lark', 'feishu', '飞书定制',
    # 通用办公类
    '移动办公', '协同办公', 'OA办公', '政务办公',
    '移动政务', 'mobile office', '企业办公app',
    # 细分搜索
    '鄂汇办', '苏政通', '豫政通', '闽政通',
    '浙里办', '粤省事', '皖事通',
    '国企通', '企业通', '工作台',
]

print(f"APKPure搜索测试 - {len(keywords)}个关键词")
print("=" * 70)

for kw in keywords:
    try:
        r = client.get(f'https://apkpure.com/cn/search?q={kw}', headers=UA)
        if r.status_code != 200:
            print(f"  [{kw}] HTTP {r.status_code}")
            continue
        
        soup = BeautifulSoup(r.text, 'lxml')
        
        # 方法1: 从链接中提取包名
        found = 0
        for a in soup.select('a[href]'):
            href = a.get('href', '')
            # APKPure详情页格式: /cn/应用名/包名 或 /应用名/包名
            m = re.search(r'/(cn/)?[^/]+/(com\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z0-9_]+)+)(?:\?|$|/)', href)
            if not m:
                m = re.search(r'/(cn/)?[^/]+/(com\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z0-9_]+)+)', href)
            if m:
                pkg = m.group(2)
                # 排除已知的非应用包名
                skip_pkgs = {'com.android.chrome', 'com.google.android.gms'}
                if pkg in skip_pkgs:
                    continue
                if pkg not in all_apps:
                    # 获取应用名
                    name = a.get_text(strip=True)
                    if not name or len(name) > 50:
                        # 从附近元素获取
                        parent = a.find_parent('div')
                        if parent:
                            p_tag = parent.select_one('p, .title, h3')
                            if p_tag:
                                name = p_tag.get_text(strip=True)
                    
                    all_apps[pkg] = {
                        'name': name[:50] if name else pkg,
                        'keyword': kw,
                        'url': href if href.startswith('http') else f'https://apkpure.com{href}',
                    }
                    found += 1
        
        # 方法2: 也查找org.和cn.开头的包
        for a in soup.select('a[href]'):
            href = a.get('href', '')
            for prefix in ['org.', 'cn.', 'io.']:
                m = re.search(rf'/(cn/)?[^/]+/({re.escape(prefix)}[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z0-9_]+)+)', href)
                if m:
                    pkg = m.group(2)
                    if pkg not in all_apps:
                        name = a.get_text(strip=True)
                        all_apps[pkg] = {
                            'name': name[:50] if name else pkg,
                            'keyword': kw,
                            'url': href if href.startswith('http') else f'https://apkpure.com{href}',
                        }
                        found += 1
        
        if found > 0:
            print(f"  [{kw}] 新发现 {found} 个包名")
        
        time.sleep(1)  # rate limiting
        
    except Exception as e:
        print(f"  [{kw}] 错误: {e}")

print(f"\n{'='*70}")
print(f"APKPure总共发现 {len(all_apps)} 个唯一包名")
print(f"{'='*70}")

# 按类别分类
wework_related = []
dingtalk_related = []
lark_related = []
office_related = []
gov_related = []
other = []

for pkg, info in sorted(all_apps.items()):
    name = info['name'].lower()
    pkg_lower = pkg.lower()
    
    if 'wework' in pkg_lower or 'wecom' in pkg_lower or '企业微信' in name:
        wework_related.append((pkg, info))
    elif 'rimet' in pkg_lower or 'dingtalk' in pkg_lower or '钉钉' in name:
        dingtalk_related.append((pkg, info))
    elif 'lark' in pkg_lower or 'feishu' in pkg_lower or '飞书' in name:
        lark_related.append((pkg, info))
    elif any(k in name for k in ['办公', 'office', 'oa', '协同', '政务', '工作']):
        office_related.append((pkg, info))
    elif any(k in name for k in ['政', '省', '浙', '粤', '赣', '鄂', '苏', '豫', '闽', '皖']):
        gov_related.append((pkg, info))
    else:
        other.append((pkg, info))

print(f"\n--- 企业微信相关 ({len(wework_related)}) ---")
for pkg, info in wework_related:
    print(f"  {pkg:50s} | {info['name'][:30]:30s} | kw={info['keyword']}")

print(f"\n--- 钉钉相关 ({len(dingtalk_related)}) ---")
for pkg, info in dingtalk_related:
    print(f"  {pkg:50s} | {info['name'][:30]:30s} | kw={info['keyword']}")

print(f"\n--- 飞书相关 ({len(lark_related)}) ---")
for pkg, info in lark_related:
    print(f"  {pkg:50s} | {info['name'][:30]:30s} | kw={info['keyword']}")

print(f"\n--- 办公/政务相关 ({len(office_related) + len(gov_related)}) ---")
for pkg, info in office_related + gov_related:
    print(f"  {pkg:50s} | {info['name'][:30]:30s} | kw={info['keyword']}")

print(f"\n--- 其他 ({len(other)}) ---")
for pkg, info in other[:20]:
    print(f"  {pkg:50s} | {info['name'][:30]:30s} | kw={info['keyword']}")
if len(other) > 20:
    print(f"  ... 还有 {len(other)-20} 个")

client.close()
