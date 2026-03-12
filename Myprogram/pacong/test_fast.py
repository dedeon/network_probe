"""快速批量测试 - 只测试确定可行的渠道"""
import httpx
import re
import json
import time
from bs4 import BeautifulSoup

client = httpx.Client(timeout=15, follow_redirects=True, verify=False)
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'}

# ====== 测试1: 大批量应用宝详情页测试 ======
print("测试1: 应用宝详情页批量测试")
print("=" * 60)

# 预先收集的可能的包名列表（从公开信息整理）
all_test_pkgs = [
    # 企业微信
    ('com.tencent.wework', '企业微信'),
    # 钉钉
    ('com.alibaba.android.rimet', '钉钉'),
    ('com.alibaba.dingtalk.global', '钉钉国际版'),
    # 飞书
    ('com.ss.android.lark', '飞书'),
    ('com.larksuite.suite', 'Lark'),
    # 政务/办公
    ('cn.gov.zj.ztzwfw', '浙里办'),
    ('com.hundsun.zjzwfw', '浙政钉'),
    ('cn.gov.gd.gzjkyy', '粤省事'),
    ('com.ecitic.bank.mobile', '中信银行'),
    ('com.chinamworld.bocmbci', '中国银行'),
    ('com.chinamworld.klb', '昆仑银行'),
    ('com.icbc', '工商银行'),
    ('com.cmb.pb', '招商银行'),
    ('com.pingan.papd', '平安银行'),
    ('com.csii.abc', '农业银行'),
    ('com.ccb.smartapp', '建设银行'),
    # 办公协同类
    ('com.tencent.docs', '腾讯文档'),
    ('com.tencent.meeting', '腾讯会议'),
    ('com.alibaba.teambition', 'Teambition'),
    ('cn.wps.moffice_eng', 'WPS Office'),
    ('com.microsoft.teams', 'Microsoft Teams'),
    ('com.microsoft.office.outlook', 'Outlook'),
    ('com.microsoft.skydrive', 'OneDrive'),
    ('com.tencent.tim', 'TIM'),
    ('com.tencent.mm', '微信'),
    ('com.tencent.mobileqq', 'QQ'),
    ('com.huawei.works', '华为WeLink'),
    ('com.huawei.welink', 'WeLink'),
    # 政务通系列
    ('cn.gov.jx.zwtb', '赣服通'),
    ('cn.gov.hunan.xzsp', '新湖南'),
    ('cn.gov.fujian.mzfw', '闽政通'),
    ('cn.gov.ah.zzfw', '皖事通'),
    ('com.inspur.emmcloud', '浪潮云+'),
    ('com.yonyou.mobile', '用友云'),
    ('com.kingdee.eas', '金蝶EAS'),
    ('com.seeyon.cmp', '致远互联'),
    ('com.landray.ekp', '蓝凌'),
    ('com.weaver.em', '泛微e-cology'),
    ('com.weaver.emobile', '泛微eMobile'),
    ('com.tongda.oapp', '通达OA'),
    ('com.fanwei.oa', '泛微OA'),
    ('com.seeyon.a8', '致远A8'),
    ('com.yidian.oa', '亿点OA'),
    ('com.kingdee.yunzhijia', '云之家'),
    ('com.chanjet.worktogether', '畅捷通工作圈'),
    ('com.bytedance.ies.xigua', '西瓜视频'),
    ('com.zhaopin.social', '智联招聘'),
    ('com.nowcoder.app.florida', '牛客'),
    ('com.yonyou.yht', '友户通'),
    ('com.cai.work', '才到工作'),
    ('com.inspur.oa', '浪潮OA'),
]

found_on_yingyongbao = []
for pkg, expected_name in all_test_pkgs:
    try:
        url = f'https://sj.qq.com/appdetail/{pkg}'
        r = client.get(url, headers=UA, follow_redirects=True)
        if r.status_code == 200 and len(r.text) > 2000:
            soup = BeautifulSoup(r.text, 'lxml')
            title = soup.select_one('title')
            tt = title.get_text(strip=True) if title else ''
            if '找不到' not in tt and '404' not in tt and len(tt) > 5:
                app_name = tt.split('app')[0].strip()
                if not app_name or app_name == '应用宝' or len(app_name) < 2:
                    app_name = tt.split('下载')[0].strip()
                if app_name and app_name != '应用宝':
                    # 从NEXT_DATA提取更多信息
                    dev = ''
                    dl_count = ''
                    ver = ''
                    nd_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
                    if nd_match:
                        try:
                            nd = json.loads(nd_match.group(1))
                            pp = nd.get('props', {}).get('pageProps', {})
                            dcr = pp.get('dynamicCardResponse', {})
                            data = dcr.get('data', {})
                            for comp in data.get('components', []):
                                cd = comp.get('data', {})
                                if isinstance(cd, dict):
                                    dev = cd.get('authorName', '') or dev
                                    dl_count = str(cd.get('appDownCount', '')) or dl_count
                                    ver = cd.get('versionName', '') or ver
                        except:
                            pass
                    
                    found_on_yingyongbao.append({
                        'package_name': pkg,
                        'app_name': app_name,
                        'developer': dev,
                        'download_count': dl_count,
                        'version': ver,
                    })
                    print(f"  ✓ {pkg:45s} | {app_name:15s} | dev={dev[:20]} | v={ver} | dl={dl_count}")
                    continue
        print(f"  ✗ {pkg} (不存在)")
    except Exception as e:
        print(f"  ✗ {pkg} (错误: {e})")
    time.sleep(0.3)

print(f"\n应用宝共找到 {len(found_on_yingyongbao)} 个应用")

# ====== 测试2: APKPure单次搜索(验证是否解封) ======
print("\n" + "=" * 60)
print("测试2: APKPure搜索")
print("=" * 60)

time.sleep(5)  # 等待冷却
apkpure_found = []
for kw in ['wework', 'dingtalk', 'lark', '政务', 'office']:
    try:
        time.sleep(5)
        r = client.get(f'https://apkpure.com/cn/search?q={kw}', headers=UA)
        if r.status_code == 200:
            pkgs = set()
            for m in re.finditer(r'/(cn/)?[^/]+/((?:com|cn|org)\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z0-9_]+)+)', r.text):
                pkg = m.group(2)
                if not any(pkg.startswith(s) for s in ['com.google', 'com.android']):
                    pkgs.add(pkg)
            print(f"  [{kw}] {len(pkgs)} 包名: {list(pkgs)[:5]}")
            for p in pkgs:
                apkpure_found.append(p)
        else:
            print(f"  [{kw}] HTTP {r.status_code}")
    except Exception as e:
        print(f"  [{kw}] Error: {e}")

print(f"\nAPKPure共找到 {len(set(apkpure_found))} 个唯一包名")

# ====== 测试3: 必应搜索包名 ======
print("\n" + "=" * 60)
print("测试3: 必应搜索")
print("=" * 60)

bing_kws = [
    '"浙政钉" apk android 包名 com.',
    '"粤省事" android 包名',
    '"浙里办" android 包名 cn.gov',
    '"皖事通" android 包名',
    '"闽政通" android apk 包名',
    '"随申办" android 包名',
    '"津心办" android 包名',
    '"爱山东" android apk',
]

for query in bing_kws:
    try:
        time.sleep(2)
        r = client.get('https://cn.bing.com/search', params={'q': query}, headers=UA)
        if r.status_code == 200:
            pkg_matches = re.findall(r'\b((?:com|cn|org)\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9_]*){1,5})\b', r.text)
            skip = ['com.google', 'com.microsoft.bing', 'com.android', 'cn.bing', 'com.bing']
            pkg_matches = [p for p in pkg_matches if not any(p.startswith(s) for s in skip)]
            pkg_matches = list(dict.fromkeys(pkg_matches))
            if pkg_matches:
                print(f"  [{query[:40]}] 包名: {pkg_matches[:5]}")
        else:
            print(f"  [{query[:40]}] HTTP {r.status_code}")
    except Exception as e:
        print(f"  [{query[:40]}] Error: {e}")

client.close()
print(f"\n最终汇总: 应用宝{len(found_on_yingyongbao)}个")
