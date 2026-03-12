#!/usr/bin/env python3
"""
对应用宝404的54个定制包名，尝试多种备选途径获取信息:
1. 小米应用商店
2. OPPO应用商店 
3. vivo应用商店
4. 百度手机助手
5. 如果所有商店都找不到，基于包名规律构造基本信息（标注为推断数据）
"""
import httpx
import re
import json
import time
import random
import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from storage.db import AppInfoDB

FAIL_404 = [
    # 飞书定制 - 33个
    'com.ss.android.lark.kaahyz17', 'com.ss.android.lark.kahzyx88',
    'com.ss.android.lark.kazdtq', 'com.ss.android.lark.kazsy73',
    'com.ss.android.lark.dabcsy97', 'com.ss.android.lark.dagtjt11',
    'com.ss.android.lark.dahngd31', 'com.ss.android.lark.dai39dl9',
    'com.ss.android.lark.dajzjt26', 'com.ss.android.lark.dajzkx436',
    'com.ss.android.lark.dastw29', 'com.ss.android.lark.greentown',
    'com.ss.android.lark.hongyuntong', 'com.ss.android.lark.htone',
    'com.ss.android.lark.ihaier', 'com.ss.android.lark.jxlh',
    'com.ss.android.lark.mdzh', 'com.ss.android.lark.pls',
    'com.ss.android.lark.sacbdn67new', 'com.ss.android.lark.sahlzj17',
    'com.ss.android.lark.samhzo3j', 'com.ss.android.lark.sapdl18',
    'com.ss.android.lark.sarq2tpv', 'com.ss.android.lark.saxdz51',
    'com.ss.android.lark.saxmsa', 'com.ss.android.lark.saxmsa667',
    'com.ss.android.lark.weifu', 'com.ss.android.lark.ce',
    'com.ss.android.lark.kacf', 'com.ss.android.lark.kacw',
    'com.ss.android.lark.sc', 'com.ss.android.lark.kalanhe',
    'com.ss.android.lark.kanewhope',
    # 钉钉定制 - 12个
    'com.alibaba.android.rimet.adt', 'com.alibaba.android.rimet.aliding',
    'com.alibaba.android.rimet.bgyfw', 'com.alibaba.android.rimet.catlcome',
    'com.alibaba.android.rimet.ccflink', 'com.alibaba.android.rimet.czd',
    'com.alibaba.android.rimet.diswu', 'com.alibaba.android.rimet.fdyfn',
    'com.alibaba.android.rimet.fosun', 'com.alibaba.android.rimet.rimm',
    'com.alibaba.android.rimet.zj', 'com.alibaba.android.rimet.edu',
    # 浙政钉/taurus - 9个
    'com.alibaba.taurus.changchun', 'com.alibaba.taurus.cpic',
    'com.alibaba.taurus.fujian', 'com.alibaba.taurus.hengdadingems',
    'com.alibaba.taurus.jiangxi', 'com.alibaba.taurus.ningxia',
    'com.alibaba.taurus.qzt', 'com.alibaba.taurus.xxxs',
    'com.alibaba.taurus.anhui',
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


def try_xiaomi(client, pkg):
    """尝试小米应用商店"""
    try:
        url = f'https://app.mi.com/details?id={pkg}'
        r = client.get(url, timeout=15)
        if r.status_code == 200 and len(r.text) > 5000:
            m = re.search(r'<title>(.*?)</title>', r.text)
            if m:
                title = m.group(1).strip()
                if title and '应用未收录' not in title and '404' not in title:
                    name = re.sub(r'\s*-\s*小米应用商店.*$', '', title).strip()
                    if name and len(name) >= 1:
                        return {'app_name': name, 'source_site': '小米应用商店', 'source_url': url}
    except:
        pass
    return None


def try_baidu_apk(client, pkg):
    """尝试百度手机助手"""
    try:
        url = f'https://shouji.baidu.com/software/{pkg}.html'
        r = client.get(url, timeout=15)
        if r.status_code == 200 and len(r.text) > 3000:
            m = re.search(r'<title>(.*?)</title>', r.text)
            if m:
                title = m.group(1).strip()
                if '百度手机助手' in title or '免费下载' in title:
                    name = re.sub(r'\s*[-_]\s*(免费下载|百度手机助手).*$', '', title).strip()
                    if name and len(name) >= 1:
                        dev_m = re.search(r'开发者：\s*(.*?)\s*<', r.text)
                        info = {'app_name': name, 'source_site': '百度手机助手', 'source_url': url}
                        if dev_m:
                            info['developer'] = dev_m.group(1).strip()
                        return info
    except:
        pass
    return None


def try_oppo(client, pkg):
    """尝试OPPO应用商店"""
    try:
        # OPPO软件商店搜索API
        url = f'https://store.oppo.com/search?q={pkg}'
        r = client.get(url, timeout=15)
        if r.status_code == 200 and len(r.text) > 3000:
            # 检查是否有结果
            if pkg in r.text:
                m = re.search(r'"appName"\s*:\s*"(.*?)"', r.text)
                if m:
                    return {'app_name': m.group(1), 'source_site': 'OPPO应用商店', 'source_url': url}
    except:
        pass
    return None


def try_search_engine(client, pkg):
    """通过搜索引擎(bing)搜索包名，提取基本信息"""
    try:
        q = f'{pkg} 安卓应用'
        url = f'https://www.bing.com/search?q={q}'
        r = client.get(url, timeout=15)
        if r.status_code == 200:
            # 从搜索结果中提取应用名
            # 查找类似 "XXX app" 或 "XXX - 安卓应用下载" 的模式
            results = re.findall(r'<h2[^>]*><a[^>]*>(.*?)</a></h2>', r.text, re.DOTALL)
            for res in results[:5]:
                res = re.sub(r'<.*?>', '', res).strip()
                if any(kw in res for kw in ['下载', '应用', 'app', 'APP', '安装', '安卓']):
                    name = re.sub(r'\s*([-–_|]|下载|安装|免费|最新|安卓|app|APP).*$', '', res).strip()
                    if name and len(name) >= 2 and len(name) <= 20:
                        return {'app_name': name, 'source_site': 'web_search', 'source_url': url}
    except:
        pass
    return None


def infer_from_package_name(pkg):
    """
    根据包名规律推断应用信息（最后的兜底方案）
    飞书定制包: com.ss.android.lark.XXX -> 飞书定制版(XXX)
    钉钉定制包: com.alibaba.android.rimet.XXX -> 钉钉定制版(XXX)
    浙政钉: com.alibaba.taurus.XXX -> 浙政钉-XXX版
    """
    info = {'package_name': pkg, 'source_site': '推断数据', 'source_url': ''}
    
    if pkg.startswith('com.ss.android.lark.'):
        suffix = pkg.replace('com.ss.android.lark.', '')
        info['app_name'] = f'飞书定制版({suffix})'
        info['product_line'] = '飞书'
        info['developer'] = '北京飞书科技有限公司'
        info['enterprise_name'] = '北京字节跳动科技有限公司'
        info['discovery_method'] = 'inferred_feishu_custom'
        info['description'] = f'飞书企业定制版本，包名后缀:{suffix}。这是基于飞书(com.ss.android.lark)的企业专属定制安卓包。'
        
        # 尝试基于后缀推断企业名
        suffix_map = {
            'greentown': ('绿城飞书', '绿城集团'),
            'hongyuntong': ('鸿运通', ''),
            'htone': ('H-One飞书', ''),
            'ihaier': ('海尔飞书', '海尔集团'),
            'jxlh': ('江西联合飞书', ''),
            'mdzh': ('美的智慧飞书', '美的集团'),
            'pls': ('普洛斯飞书', '普洛斯'),
            'weifu': ('威孚飞书', '无锡威孚高科技集团'),
            'ce': ('飞书CE版', ''),
            'sc': ('飞书SC版', ''),
            'kacf': ('长丰飞书', ''),
            'kacw': ('长旺飞书', ''),
            'kanewhope': ('新希望飞书', '新希望集团'),
            'kalanhe': ('蓝河飞书', ''),
            'rongchuang': ('融创飞书', '融创中国'),
            'kaahyz17': ('飞书定制(kaahyz17)', ''),
            'kahzyx88': ('飞书定制(kahzyx88)', ''),
            'kazdtq': ('飞书定制(kazdtq)', ''),
            'kazsy73': ('飞书定制(kazsy73)', ''),
            'kacrc': ('工作说说', ''),
            'kami': ('飞书定制(kami)', ''),
        }
        if suffix in suffix_map:
            info['app_name'] = suffix_map[suffix][0]
            if suffix_map[suffix][1]:
                info['enterprise_name'] = suffix_map[suffix][1]
                
    elif pkg.startswith('com.alibaba.android.rimet.'):
        suffix = pkg.replace('com.alibaba.android.rimet.', '')
        info['app_name'] = f'钉钉定制版({suffix})'
        info['product_line'] = '钉钉'
        info['developer'] = '钉钉（中国）信息技术有限公司'
        info['enterprise_name'] = '阿里巴巴集团'
        info['discovery_method'] = 'inferred_dingding_custom'
        info['description'] = f'钉钉企业定制版本，包名后缀:{suffix}。这是基于钉钉(com.alibaba.android.rimet)的企业专属定制安卓包。'
        
        suffix_map = {
            'adt': ('钉钉ADT版', ''),
            'aliding': ('阿里钉', '阿里巴巴'),
            'bgyfw': ('碧桂园服务钉钉', '碧桂园服务'),
            'catlcome': ('CATL钉钉', '宁德时代'),
            'ccflink': ('中汽联钉钉', ''),
            'czd': ('楚政钉', ''),
            'diswu': ('钉钉DISWU版', ''),
            'fdyfn': ('钉钉定制(fdyfn)', ''),
            'fosun': ('复星钉钉', '复星集团'),
            'rimm': ('钉钉RIMM版', ''),
            'zj': ('浙江钉钉', ''),
            'edu': ('钉钉教育版', ''),
        }
        if suffix in suffix_map:
            info['app_name'] = suffix_map[suffix][0]
            if suffix_map[suffix][1]:
                info['enterprise_name'] = suffix_map[suffix][1]
                
    elif pkg.startswith('com.alibaba.taurus.'):
        suffix = pkg.replace('com.alibaba.taurus.', '')
        info['app_name'] = f'浙政钉-{suffix}版'
        info['product_line'] = '钉钉'
        info['developer'] = '钉钉（中国）信息技术有限公司'
        info['enterprise_name'] = '阿里巴巴集团'
        info['discovery_method'] = 'inferred_taurus_custom'
        info['description'] = f'政务钉钉(浙政钉)地方定制版本，后缀:{suffix}。基于com.alibaba.taurus的政务专属定制安卓包。'
        
        suffix_map = {
            'changchun': ('长春政务钉钉', '长春市人民政府'),
            'cpic': ('太保政务钉钉', '中国太平洋保险'),
            'fujian': ('闽政通', '福建省人民政府'),
            'hengdadingems': ('恒大政务钉钉', ''),
            'jiangxi': ('赣政通', '江西省人民政府'),
            'ningxia': ('宁政通', '宁夏回族自治区人民政府'),
            'qzt': ('黔政通', '贵州省人民政府'),
            'xxxs': ('新政通', ''),
            'anhui': ('皖政通', '安徽省人民政府'),
        }
        if suffix in suffix_map:
            info['app_name'] = suffix_map[suffix][0]
            if suffix_map[suffix][1]:
                info['enterprise_name'] = suffix_map[suffix][1]
    
    return info


def main():
    db = AppInfoDB()
    client = httpx.Client(timeout=20, follow_redirects=True, verify=False, headers=HEADERS)
    
    # 检查已有的
    existing = set()
    conn = sqlite3.connect('output/results.db')
    c = conn.cursor()
    for row in c.execute('SELECT package_name FROM app_info'):
        existing.add(row[0])
    conn.close()
    
    total = len(FAIL_404)
    ok_xiaomi = 0
    ok_baidu = 0
    ok_search = 0
    ok_inferred = 0
    still_missing = []
    
    print(f"尝试从其他来源获取 {total} 个应用宝404包名的信息...")
    print(f"数据库已有 {len(existing)} 条记录")
    print()
    
    for i, pkg in enumerate(FAIL_404):
        if pkg in existing:
            print(f"[{i+1}/{total}] SKIP {pkg} (已存在)")
            continue
        
        info = None
        source = None
        
        # 1. 尝试小米
        info = try_xiaomi(client, pkg)
        if info:
            source = '小米'
            ok_xiaomi += 1
        
        # 2. 尝试百度手机助手
        if not info:
            time.sleep(0.5)
            info = try_baidu_apk(client, pkg)
            if info:
                source = '百度'
                ok_baidu += 1
        
        # 3. 尝试搜索引擎
        if not info:
            time.sleep(0.5)
            info = try_search_engine(client, pkg)
            if info:
                source = '搜索'
                ok_search += 1
        
        # 4. 兜底：基于包名推断
        if not info:
            info = infer_from_package_name(pkg)
            source = '推断'
            ok_inferred += 1
        
        # 确定产品线
        if 'lark' in pkg:
            pl = '飞书'
        elif 'rimet' in pkg:
            pl = '钉钉'
        elif 'taurus' in pkg:
            pl = '钉钉'
        else:
            pl = '办公协同'
        
        if not info.get('product_line'):
            info['product_line'] = pl
        if not info.get('discovery_method'):
            info['discovery_method'] = f'fallback_{source}'
        info['package_name'] = pkg
        
        try:
            ok = db.insert_app(
                package_name=pkg,
                app_name=info.get('app_name', ''),
                product_line=info.get('product_line', pl),
                enterprise_name=info.get('enterprise_name', ''),
                developer=info.get('developer', ''),
                version=info.get('version', ''),
                version_code='',
                update_date='',
                download_count=info.get('download_count', ''),
                description=info.get('description', ''),
                source_site=info.get('source_site', '推断数据'),
                source_url=info.get('source_url', ''),
                discovery_method=info.get('discovery_method', f'fallback_{source}'),
            )
            if ok:
                existing.add(pkg)
                print(f"[{i+1}/{total}] ✅ [{source:4s}] {pkg} -> {info.get('app_name', '?')} ({pl})")
            else:
                print(f"[{i+1}/{total}] ⚠️  {pkg} -> 插入失败")
        except Exception as e:
            print(f"[{i+1}/{total}] ❌ {pkg} -> DB error: {e}")
        
        time.sleep(random.uniform(0.3, 0.8))
    
    # === 汇总 ===
    print()
    print("=" * 60)
    print("备选来源爬取汇总")
    print("=" * 60)
    print(f"总共: {total} 个404包名")
    print(f"小米成功: {ok_xiaomi}")
    print(f"百度成功: {ok_baidu}")
    print(f"搜索成功: {ok_search}")
    print(f"推断入库: {ok_inferred}")
    
    # 质量评分和导出
    print()
    print("执行质量评分和导出...")
    try:
        from pipeline.quality_scorer import QualityScorer
        from storage.db import CustomerDB
        from storage.exporter import DataExporter
        QualityScorer(db).run()
        cdb = CustomerDB()
        exp = DataExporter(cdb, db)
        for nm, pa in exp.export_all().items():
            print(f"  导出: {nm} -> {pa}")
        exp.print_summary()
        cdb.close()
    except Exception as e:
        print(f"导出失败: {e}")
    
    db.close()
    client.close()
    print("\n完成!")


if __name__ == '__main__':
    main()
