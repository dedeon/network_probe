#!/usr/bin/env python3
"""诊断失败包名"""
import httpx, re, json, time, random, sys

FAILED = [
    'com.tencent.mobileqq','com.tencent.mm','com.tencent.qqmail','com.tencent.map',
    'com.tencent.qqlive','com.tencent.qqmusic','com.tencent.karaoke','com.tencent.weishi',
    'com.tencent.news','com.tencent.mtt','com.tencent.wetype','com.tencent.reading',
    'com.tencent.androidqqmanager',
    'com.eg.android.AlipayGphone','com.taobao.idlefish','com.alibaba.wireless.ichangmessenger',
    'com.tmall.wireless','com.UCMobile','com.autonavi.minimap','com.youku.phone',
    'com.taobao.trip','com.cainiao.wireless.homepage','com.alibaba.teambition',
    'com.ss.android.ugc.aweme','com.ss.android.ugc.aweme.lite','com.ss.android.article.lite',
    'com.ss.android.ugc.live','com.ss.android.auto','com.ss.android.article.video','com.luna.music',
    'cn.wps.moffice_eng','cn.wps.yun','com.microsoft.office.onenote',
    'cmb.pb','com.chinamworld.main','com.android.bankabc','com.bankcomm.Bankcomm',
    'com.yitong.mbank.psbc','com.spdb.mobilebankN','com.cib.cibmb',
    'com.hpbr.bosszhipin','com.youdao.note','com.baidu.netdisk',
    'com.sina.weibo','com.zhihu.android','tv.danmaku.bili','com.xingin.xhs',
    'com.baidu.searchbox','com.baidu.BaiduMap','com.baidu.input','com.iflytek.inputmethod',
    'com.sdu.didi.psnger','ctrip.android.view','com.MobileTicket','com.netease.cloudmusic','com.kuaishou.nebula',
    'com.jingdong.app.mall','com.xunmeng.pinduoduo','com.meituan','com.dianping.v1','com.sankuai.meituan.takeoutnew',
    'com.qiyi.video','com.kugou.android','com.ximalaya.ting.android','com.hunantv.imgo.activity',
    'com.todesk','com.oray.sunlogin','com.youdao.dict','com.camscanner.online',
    'com.eastmoney.android.berlin','com.hexin.plat.android','com.chinaums.pmp','com.sf.activity',
    'com.xunlei.downloadprovider','com.cubic.autohome','com.fenbi.android.servant','com.chaoxing.mobile',
    'us.zoom.videomeetings','com.gotokeep.keep','com.tongcheng.android','com.baidu.translate',
    'com.netease.newsreader.activity','com.suning.mobile.ebuy',
]

cl = httpx.Client(timeout=15, follow_redirects=True, verify=False,
    headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
             'Accept-Language':'zh-CN,zh;q=0.9'})

stats = {'ok':0,'http_err':0,'short':0,'no_next':0,'no_gd':0,'empty_items':0,'exc':0}
ok_list = []
fail_detail = []

for i, pkg in enumerate(FAILED):
    try:
        url = f'https://sj.qq.com/appdetail/{pkg}'
        r = cl.get(url)
        if r.status_code != 200:
            print(f'HTTP_{r.status_code} {pkg}')
            stats['http_err'] += 1
            fail_detail.append((pkg, f'http_{r.status_code}'))
            time.sleep(0.3)
            continue
        txt = r.text
        if len(txt) < 2000:
            print(f'SHORT    {pkg}  len={len(txt)}')
            stats['short'] += 1
            fail_detail.append((pkg, f'short_{len(txt)}'))
            time.sleep(0.3)
            continue
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', txt, re.DOTALL)
        if not m:
            print(f'NO_NEXT  {pkg}')
            stats['no_next'] += 1
            fail_detail.append((pkg, 'no_next_data'))
            time.sleep(0.3)
            continue
        nd = json.loads(m.group(1))
        pp = nd.get('props', {}).get('pageProps', {})
        dcr = pp.get('dynamicCardResponse', {}).get('data', {})
        found = False
        app_name = None
        if isinstance(dcr, dict):
            for comp in dcr.get('components', []):
                cd = comp.get('data', {})
                if not isinstance(cd, dict):
                    continue
                if cd.get('name') == 'GameDetail':
                    found = True
                    items = cd.get('itemData', [])
                    if isinstance(items, str):
                        items = json.loads(items)
                    if isinstance(items, list) and items:
                        it = items[0]
                        app_name = it.get('name', '?')
                        print(f'OK       {pkg:45s} -> {app_name}')
                        stats['ok'] += 1
                        ok_list.append(pkg)
                    else:
                        print(f'EMPTY_IT {pkg}')
                        stats['empty_items'] += 1
                        fail_detail.append((pkg, 'empty_itemData'))
                    break
        if not found:
            # Check for title fallback
            comps = []
            if isinstance(dcr, dict):
                for comp in dcr.get('components', []):
                    cd = comp.get('data', {})
                    if isinstance(cd, dict):
                        comps.append(cd.get('name', '?'))
            # Also check seoMeta title
            seo = pp.get('seoMeta', {})
            seo_title = seo.get('title', '')
            if seo_title and '找不到' not in seo_title and '404' not in seo_title:
                print(f'SEO_OK   {pkg:45s} -> seo_title={seo_title[:40]}  comps={comps}')
                stats['ok'] += 1
                ok_list.append(pkg)
            else:
                print(f'NO_GD    {pkg:45s} comps={comps} seo={seo_title[:40] if seo_title else "none"}')
                stats['no_gd'] += 1
                fail_detail.append((pkg, f'no_gamedetail_comps={comps}'))
    except Exception as e:
        print(f'EXC      {pkg}  {str(e)[:60]}')
        stats['exc'] += 1
        fail_detail.append((pkg, f'exc:{str(e)[:40]}'))
    time.sleep(0.3)

cl.close()

print(f'\n{"="*60}')
print(f'诊断结果: 共{len(FAILED)}个')
for k, v in stats.items():
    print(f'  {k:15s}: {v}')
print(f'\nOK包名({len(ok_list)}):')
for p in ok_list:
    print(f'  {p}')
print(f'\n失败详情({len(fail_detail)}):')
for p, reason in fail_detail:
    print(f'  {p:45s} {reason}')
