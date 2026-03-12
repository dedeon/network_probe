#!/usr/bin/env python3
"""测试direct_crawler中_fetch_yingyongbao_detail的具体解析逻辑"""
import httpx, re, json
from bs4 import BeautifulSoup

c = httpx.Client(timeout=20, follow_redirects=True, verify=False,
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})

test_pkgs = [
    # 这些之前应该成功但没成功的
    'cn.wps.moffice_eng',    # WPS
    'com.tencent.mobileqq',  # QQ  
    'com.tencent.mm',        # 微信
    'cmb.pb',                # 招商银行
    'com.chinamworld.main',  # 建设银行
    'com.android.bankabc',   # 农行
    'com.tencent.qqmusic',   # QQ音乐
    # 这些之前确认成功的
    'com.tencent.wework',    # 企业微信
    'com.alibaba.android.rimet', # 钉钉
]

for pkg in test_pkgs:
    url = f'https://sj.qq.com/appdetail/{pkg}'
    resp = c.get(url)
    
    # 模拟 _fetch_yingyongbao_detail 的逻辑
    if resp.status_code != 200 or len(resp.text) < 2000:
        print(f'{pkg}: FAILED - status={resp.status_code} len={len(resp.text)}')
        continue
    
    soup = BeautifulSoup(resp.text, 'lxml')
    title = soup.select_one('title')
    tt = title.get_text(strip=True) if title else ''
    
    if '找不到' in tt or '404' in tt or len(tt) < 5:
        print(f'{pkg}: FAILED - title check: "{tt[:50]}"')
        continue
    
    # 提取应用名
    app_name = tt.split('app')[0].strip()
    if not app_name or app_name == '应用宝' or len(app_name) < 2:
        app_name = tt.split('下载')[0].strip()
    if not app_name or app_name == '应用宝':
        app_name = tt.split('官方')[0].strip()
    if app_name and '应用宝' not in app_name:
        app_name = re.sub(r'(官方版|最新版|安卓版|手机版).*$', '', app_name).strip()
        app_name = re.sub(r'-.*$', '', app_name).strip()
        final_name = app_name
    else:
        final_name = None
    
    # Also check __NEXT_DATA__
    nd_name = None
    nd_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
    if nd_match:
        try:
            nd = json.loads(nd_match.group(1))
            pp = nd.get('props', {}).get('pageProps', {})
            dcr = pp.get('dynamicCardResponse', {})
            data = dcr.get('data', {})
            if isinstance(data, dict):
                for comp in data.get('components', []):
                    cd = comp.get('data', {})
                    if isinstance(cd, dict) and cd.get('appName'):
                        nd_name = cd['appName']
                        break
        except:
            pass
    
    print(f'{pkg}: title="{tt[:60]}" | from_title="{final_name}" | from_next="{nd_name}" | RESULT={"OK" if final_name or nd_name else "FAIL"}')

c.close()
