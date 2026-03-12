"""全面测试所有可能的数据源获取应用信息"""
import httpx
import re
import json
import time
from bs4 import BeautifulSoup

client = httpx.Client(timeout=20, follow_redirects=True, verify=False)
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
UA_MOBILE = {'User-Agent': 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'}

results = {}  # pkg -> info

def add_result(pkg, name, product_line='', source='', url='', **extra):
    if pkg and name and not any(d in pkg for d in ['google.', 'android.com', 'gstatic']):
        if pkg not in results:
            results[pkg] = {'package_name': pkg, 'app_name': name, 'product_line': product_line, 'source': source, 'url': url}
            results[pkg].update(extra)
            return True
    return False

# ====== 1. APKPure 带延迟搜索 ======
print("=" * 60)
print("1. APKPure搜索 (带延迟)")
print("=" * 60)

apkpure_kws = ['企业微信', '钉钉', '飞书', 'wework', 'dingtalk', 'lark',
               '移动办公', '协同办公', '政务钉钉', '浙政钉', '粤政易', '浙里办', '粤省事']

for kw in apkpure_kws:
    try:
        time.sleep(3)  # 更长的延迟避免403
        r = client.get(f'https://apkpure.com/cn/search?q={kw}', headers=UA)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'lxml')
            found = 0
            for a in soup.select('a[href]'):
                href = a.get('href', '')
                for prefix in ['com.', 'cn.', 'org.', 'io.']:
                    m = re.search(rf'/(cn/)?[^/]+/({re.escape(prefix)}[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z0-9_]+)+)', href)
                    if m:
                        pkg = m.group(2)
                        name = a.get_text(strip=True)[:50]
                        if add_result(pkg, name or pkg, source='apkpure', url=f'https://apkpure.com{href}'):
                            found += 1
            print(f"  [{kw}] +{found} (total={len(results)})")
        else:
            print(f"  [{kw}] HTTP {r.status_code}")
    except Exception as e:
        print(f"  [{kw}] Error: {e}")

# ====== 2. 应用宝详情页 - 扩大已知包名列表 ======
print("\n" + "=" * 60)
print("2. 应用宝详情页 (批量已知包名)")
print("=" * 60)

known_packages = [
    # 企业微信
    'com.tencent.wework',
    # 钉钉系列
    'com.alibaba.android.rimet',
    'com.alibaba.dingtalk.global',
    # 飞书
    'com.ss.android.lark',
    'com.larksuite.suite',
    # 政务应用
    'cn.gov.zj.ztzwfw',       # 浙里办
    'cn.gov.gd.ydzy',          # 粤政易
    'cn.gov.gd.gzjkyy',        # 粤省事
    'cn.gov.jx.zwtb',          # 赣政通
    'cn.gov.hunan.hnsysb',     # 湘政通
    'cn.gov.henan.yuspeed',    # 豫事办
    'cn.gov.fujian.mzfw',      # 闽政通
    'cn.gov.ahzw.ggzyfw',      # 皖事通
    'cn.gov.sx.qzh',           # 秦政通
    'com.hundsun.zjzwfw',       # 浙政钉
    'cn.gov.zj.zjzwfw',        # 浙里办v2
    # 其他办公协同类
    'com.alibaba.alading',
    'com.alibaba.android.rimet.ep',
    'com.tencent.tim',
    'com.tencent.mtt',
    'com.kingsoft.office.pro',
    'cn.wps.moffice_eng',
    'com.kingsoft.email',
    'com.tencent.docs',
    'com.tencent.meeting',
    'com.alibaba.teambition',
    'com.microsoft.teams',
]

for pkg in known_packages:
    try:
        time.sleep(1)
        url = f'https://sj.qq.com/appdetail/{pkg}'
        r = client.get(url, headers=UA)
        if r.status_code == 200 and len(r.text) > 2000:
            soup = BeautifulSoup(r.text, 'lxml')
            title = soup.select_one('title')
            title_text = title.get_text(strip=True) if title else ''
            if '找不到' not in title_text and '404' not in title_text:
                app_name = title_text.split('app')[0].strip()
                if not app_name or app_name == '应用宝':
                    app_name = title_text.split('下载')[0].strip()
                if app_name and app_name != '应用宝':
                    add_result(pkg, app_name, source='应用宝', url=url)
                    print(f"  {pkg}: {app_name}")
                else:
                    print(f"  {pkg}: 存在但解析名称失败 ({title_text[:40]})")
            else:
                print(f"  {pkg}: 不存在")
        else:
            print(f"  {pkg}: HTTP {r.status_code}")
    except Exception as e:
        print(f"  {pkg}: Error {e}")

# ====== 3. 搜索引擎直接搜包名 ======
print("\n" + "=" * 60)
print("3. 必应搜索应用商店链接")
print("=" * 60)

bing_queries = [
    'site:apkpure.com "企业微信" OR "wework"',
    'site:apkpure.com "钉钉" OR "dingtalk"', 
    'site:apkpure.com "飞书" OR "lark"',
    'site:apkpure.com "政务钉钉" OR "浙政钉"',
    'site:apkpure.com "移动办公" OR "协同办公"',
    'site:apkpure.com "政务" "app"',
    'site:wandoujia.com "企业微信" OR "钉钉" OR "飞书"',
    '"企业微信" "com.tencent.wework" 定制版 下载',
    '"钉钉" "com.alibaba" 定制 apk',
    '"飞书" "com.ss.android" 定制 apk',
    '政务钉钉 apk android 包名',
    '浙政钉 android apk 包名 com.',
    '粤政易 android apk com.',
    '赣政通 android apk 下载',
    '浙里办 android apk 包名',
    '粤省事 android apk 包名',
    '皖事通 android apk',
    '鄂汇办 android apk',
    '闽政通 android apk',
    '豫事办 android apk',
]

for query in bing_queries:
    try:
        time.sleep(2)
        r = client.get('https://cn.bing.com/search', params={'q': query, 'count': 20}, headers=UA)
        if r.status_code == 200:
            # 从结果中提取所有包名
            text = r.text
            pkg_matches = re.findall(r'\b(com\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9_]*){1,5})\b', text)
            pkg_matches += re.findall(r'\b(cn\.gov\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9_]*){1,4})\b', text)
            pkg_matches += re.findall(r'\b(cn\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9_]*){1,5})\b', text)
            
            # 过滤
            skip = ['com.google', 'com.microsoft.bing', 'com.android', 'cn.bing.com', 'com.bing']
            pkg_matches = [p for p in pkg_matches if not any(p.startswith(s) for s in skip)]
            pkg_matches = list(dict.fromkeys(pkg_matches))
            
            if pkg_matches:
                print(f"  [{query[:50]}...] 找到包名: {pkg_matches[:5]}")
                for pkg in pkg_matches[:10]:
                    add_result(pkg, pkg, source='bing_search', url='')
        else:
            print(f"  [{query[:40]}...] HTTP {r.status_code}")
    except Exception as e:
        print(f"  [{query[:40]}...] Error: {e}")

# ====== 4. GitHub搜索已知定制包名列表 ======
print("\n" + "=" * 60) 
print("4. 搜狗搜索政务应用")
print("=" * 60)

sogou_queries = [
    '浙政钉 android 包名',
    '粤政易 android 包名',
    '赣政通 android apk',
    '鄂汇办 android apk',
    '苏政通 android 包名',
    '皖事通 android 下载',
    '浙里办 android apk',
    '粤省事 android apk',
    '闽政通 android 下载',
    '豫事办 android 包名',
    '蒙速办 android 包名',
    '辽事通 android apk',
    '吉事办 android',
    '陕政通 android',
    '甘快办 android',
    '青松办 android',
    '新政通 android',
    '爱山东 android',
    '随申办 android 包名',
    '津心办 android',
]

for query in sogou_queries:
    try:
        time.sleep(3)
        r = client.get('https://www.sogou.com/web', params={'query': query}, headers=UA)
        if r.status_code == 200:
            text = r.text
            pkg_matches = re.findall(r'\b(com\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9_]*){1,5})\b', text)
            pkg_matches += re.findall(r'\b(cn\.gov\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9_]*){1,4})\b', text)
            pkg_matches += re.findall(r'\b(cn\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9_]*){1,5})\b', text)
            
            skip = ['com.sogou', 'com.google', 'com.android', 'com.baidu', 'cn.sogou']
            pkg_matches = [p for p in pkg_matches if not any(p.startswith(s) for s in skip)]
            pkg_matches = list(dict.fromkeys(pkg_matches))
            
            if pkg_matches:
                print(f"  [{query}] 找到: {pkg_matches[:5]}")
                for pkg in pkg_matches[:10]:
                    add_result(pkg, pkg, source='sogou_search', url='')
        else:
            print(f"  [{query}] HTTP {r.status_code}")
    except Exception as e:
        print(f"  [{query}] Error: {e}")

# ====== 汇总 ======
print("\n" + "=" * 60)
print(f"总计发现 {len(results)} 个唯一包名")
print("=" * 60)
for pkg, info in sorted(results.items()):
    print(f"  {pkg:50s} | {info['app_name'][:25]:25s} | {info['source']}")

client.close()
