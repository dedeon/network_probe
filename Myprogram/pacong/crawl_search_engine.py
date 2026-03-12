#!/usr/bin/env python3
"""
通过搜索引擎和第三方APK下载站搜索54个定制包名的真实信息
策略:
1. 先通过多个第三方下载站直接搜索包名
2. 通过搜狗搜索引擎搜索
3. 从搜索结果页面提取应用名、开发者等信息
"""
import httpx
import re
import json
import time
import random
import os
import sys
import sqlite3
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from storage.db import AppInfoDB

# 54个需要通过搜索引擎获取信息的包名
INFERRED_PKGS = []

def load_inferred_pkgs():
    """从数据库加载所有source_site='包名推断'的包名"""
    conn = sqlite3.connect('output/results.db')
    c = conn.cursor()
    rows = c.execute("SELECT package_name, app_name FROM app_info WHERE source_site='包名推断'").fetchall()
    conn.close()
    return [(r[0], r[1]) for r in rows]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def search_hncj(client, pkg):
    """在火鸟手游网搜索(已确认该站收录了定制包)"""
    try:
        # 用包名搜索
        url = f'https://www.hncj.com/search/{quote(pkg)}'
        r = client.get(url, timeout=15)
        if r.status_code == 200 and len(r.text) > 3000:
            # 查找包含该包名的搜索结果
            if pkg in r.text:
                # 提取应用名和详情链接
                # 搜索结果格式: <a href="/sjrj/XXX.html">应用名</a>
                pattern = rf'<a[^>]*href="(/sjrj/\d+\.html)"[^>]*>(.*?)</a>'
                matches = re.findall(pattern, r.text, re.DOTALL)
                for link, title in matches:
                    title_clean = re.sub(r'<[^>]+>', '', title).strip()
                    if title_clean and len(title_clean) >= 2:
                        detail_url = f'https://www.hncj.com{link}'
                        return fetch_hncj_detail(client, detail_url, pkg)
    except Exception as e:
        pass
    return None


def fetch_hncj_detail(client, url, pkg):
    """获取火鸟手游网的应用详情页"""
    try:
        r = client.get(url, timeout=15)
        if r.status_code != 200:
            return None
        text = r.text
        
        info = {'source_site': '火鸟手游网', 'source_url': url}
        
        # 确认包名匹配
        if pkg not in text:
            return None
        
        # 提取应用名 - 从title或h1
        title_m = re.search(r'<title>(.*?)</title>', text)
        if title_m:
            title = title_m.group(1).strip()
            # 去除网站名后缀
            name = re.sub(r'\s*[-_|]\s*(火鸟|手游网|最新版).*$', '', title).strip()
            name = re.sub(r'(下载|安装|官方|最新).*$', '', name).strip()
            if name:
                info['app_name'] = name
        
        # 提取包名确认
        pkg_m = re.search(r'包名[：:]\s*' + re.escape(pkg), text)
        if not pkg_m:
            pkg_m = re.search(re.escape(pkg), text)
        
        # 提取版本
        ver_m = re.search(r'版本[：:]\s*(v?[\d.]+)', text)
        if ver_m:
            info['version'] = ver_m.group(1)
        
        # 提取大小
        size_m = re.search(r'大小[：:]\s*([\d.]+\s*[MG]B?)', text, re.IGNORECASE)
        
        # 提取MD5
        md5_m = re.search(r'MD5[：:]\s*([A-Fa-f0-9]{32})', text)
        
        if info.get('app_name'):
            return info
    except:
        pass
    return None


def search_anfensi(client, pkg):
    """在安粉丝网搜索"""
    try:
        url = f'https://www.anfensi.com/search/{quote(pkg)}/'
        r = client.get(url, timeout=15)
        if r.status_code == 200 and pkg in r.text:
            # 找详情页链接
            pattern = rf'<a[^>]*href="(https?://www\.anfensi\.com/down/\d+\.html)"[^>]*>(.*?)</a>'
            matches = re.findall(pattern, r.text, re.DOTALL)
            for link, title in matches:
                title_clean = re.sub(r'<[^>]+>', '', title).strip()
                if title_clean:
                    return fetch_anfensi_detail(client, link, pkg)
    except:
        pass
    return None


def fetch_anfensi_detail(client, url, pkg):
    """获取安粉丝网应用详情"""
    try:
        r = client.get(url, timeout=15)
        if r.status_code != 200 or pkg not in r.text:
            return None
        
        text = r.text
        info = {'source_site': '安粉丝网', 'source_url': url}
        
        # 提取应用名
        title_m = re.search(r'<title>(.*?)</title>', text)
        if title_m:
            title = title_m.group(1).strip()
            name = re.sub(r'\s*[-_|]\s*(安粉丝|下载|安卓).*$', '', title).strip()
            if name:
                info['app_name'] = name
        
        # h1标题
        h1_m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.DOTALL)
        if h1_m:
            h1 = re.sub(r'<[^>]+>', '', h1_m.group(1)).strip()
            if h1 and not info.get('app_name'):
                info['app_name'] = h1
        
        # 提取版本
        ver_m = re.search(r'版本[：:]\s*(v?[\d.]+)', text)
        if ver_m:
            info['version'] = ver_m.group(1)
        
        # 提取描述
        desc_m = re.search(r'应用介绍.*?<p[^>]*>(.*?)</p>', text, re.DOTALL)
        if desc_m:
            desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip()
            if desc:
                info['description'] = desc[:500]
        
        if info.get('app_name'):
            return info
    except:
        pass
    return None


def search_it168(client, pkg):
    """在IT168下载站搜索"""
    try:
        url = f'https://shike.it168.com/search?keyword={quote(pkg)}'
        r = client.get(url, timeout=15)
        if r.status_code == 200 and pkg in r.text:
            # 找详情页
            pattern = rf'<a[^>]*href="(https?://shike\.it168\.com/detail/\d+\.html)"[^>]*>(.*?)</a>'
            matches = re.findall(pattern, r.text, re.DOTALL)
            for link, title in matches:
                return fetch_it168_detail(client, link, pkg)
    except:
        pass
    return None


def fetch_it168_detail(client, url, pkg):
    """获取IT168详情"""
    try:
        r = client.get(url, timeout=15)
        if r.status_code != 200 or pkg not in r.text:
            return None
        
        text = r.text
        info = {'source_site': 'IT168', 'source_url': url}
        
        title_m = re.search(r'<title>(.*?)</title>', text)
        if title_m:
            title = title_m.group(1).strip()
            name = re.sub(r'\s*[-_|]\s*(IT168|下载站|最新版|免费).*$', '', title).strip()
            name = re.sub(r'(app|APP)\s*(最新版|免费|下载).*$', '', name).strip()
            if name:
                info['app_name'] = name
        
        ver_m = re.search(r'版本[：:]\s*(v?[\d.]+)', text)
        if ver_m:
            info['version'] = ver_m.group(1)
        
        if info.get('app_name'):
            return info
    except:
        pass
    return None


def search_sogou(client, pkg):
    """通过搜狗搜索引擎搜索包名"""
    try:
        query = quote(f'"{pkg}" 下载 安卓')
        url = f'https://www.sogou.com/web?query={query}'
        r = client.get(url, timeout=15)
        if r.status_code != 200:
            return None
        
        text = r.text
        # 从搜狗结果中找到与包名直接相关的结果
        # 提取h3标题和链接
        h3_blocks = re.findall(r'<h3[^>]*>(.*?)</h3>', text, re.DOTALL)
        
        for h3 in h3_blocks[:8]:
            h3_text = re.sub(r'<[^>]+>', '', h3).strip()
            link_m = re.search(r'href="(https?://[^"]+)"', h3)
            link = link_m.group(1) if link_m else ''
            
            # 看标题是否暗示是某个具体应用
            # 排除通用的飞书/钉钉主包结果
            if any(kw in h3_text for kw in ['飞书定时打卡', 'lark国际版', 'lark办公', '钉钉打卡虚拟', '钉钉APP官方', 'Android 实现钉钉']):
                continue
            
            # 如果标题中包含"下载"且不是通用结果，可能是定制包页面
            if ('下载' in h3_text or '安卓' in h3_text) and link:
                # 去除常见的下载站后缀，提取应用名
                name = h3_text
                name = re.sub(r'\s*[-_|–—]\s*(.*下载.*|.*安卓.*|.*最新.*|.*官方.*)$', '', name).strip()
                name = re.sub(r'(下载|安装|最新版|官方版|安卓版|手机版|app版|免费).*$', '', name, flags=re.IGNORECASE).strip()
                
                if name and len(name) >= 2 and len(name) <= 30:
                    # 排除通用结果
                    if name not in ['飞书', '钉钉', 'lark', 'Lark', '阿里钉钉']:
                        return {
                            'app_name': name,
                            'source_site': '搜狗搜索',
                            'source_url': link,
                        }
    except:
        pass
    return None


def search_bing(client, pkg):
    """通过Bing搜索包名(用引号精确搜索)"""
    try:
        query = quote(f'"{pkg}" 下载')
        url = f'https://www.bing.com/search?q={query}'
        r = client.get(url, timeout=15)
        if r.status_code != 200:
            return None
        
        text = r.text
        algos = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', text, re.DOTALL)
        
        for algo in algos[:8]:
            # 提取标题
            title_m = re.search(r'<a[^>]*href="[^"]*"[^>]*>(.*?)</a>', algo, re.DOTALL)
            if not title_m:
                continue
            raw_title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
            
            # 去掉URL部分(bing有时把URL附在标题里)
            raw_title = re.sub(r'^.*?(https?://\S+\s*)', '', raw_title).strip()
            
            # 跳过通用的飞书/钉钉结果
            if any(kw in raw_title for kw in ['com.ss.android.lark 厂商', '飞书app最新版', '飞书APP官方', '钉钉2026', '钉钉APP官方', 'Gmail', 'zhihu.com', 'launcher']):
                continue
            
            # 检查摘要中是否包含包名
            desc_m = re.search(r'<p[^>]*>(.*?)</p>', algo, re.DOTALL)
            desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip() if desc_m else ''
            
            if pkg in desc or pkg in algo:
                # 可能找到了！提取应用名
                name = raw_title
                name = re.sub(r'\s*[-_|–—]\s*(.*下载.*|.*软件.*|.*安卓.*|.*官方.*)$', '', name).strip()
                name = re.sub(r'(下载|安装|最新版|官方版|安卓版|手机版|app|APP|免费).*$', '', name, flags=re.IGNORECASE).strip()
                
                link_m = re.search(r'href="(https?://[^"]+)"', title_m.group(0))
                link = link_m.group(1) if link_m else ''
                
                if name and len(name) >= 2 and len(name) <= 30 and name not in ['飞书', '钉钉', 'lark', 'Lark']:
                    return {
                        'app_name': name,
                        'source_site': 'Bing搜索',
                        'source_url': link,
                    }
    except:
        pass
    return None


def try_direct_download_sites(client, pkg):
    """直接访问已知收录定制包的下载站"""
    sites = [
        # 格式: (url_template, site_name, parse_func)
        (f'https://www.hncj.com/sjrj/search?keyword={quote(pkg)}', '火鸟手游网', None),
        (f'http://www.anfensi.com/search/{quote(pkg)}/', '安粉丝网', None),
    ]
    
    for url, site_name, parse_fn in sites:
        try:
            r = client.get(url, timeout=15)
            if r.status_code == 200 and pkg in r.text:
                # 找到包含该包名的页面
                # 提取第一个详情链接
                if 'hncj.com' in url:
                    links = re.findall(r'href="(/sjrj/\d+\.html)"', r.text)
                    if links:
                        detail = fetch_hncj_detail(client, f'https://www.hncj.com{links[0]}', pkg)
                        if detail:
                            return detail
                elif 'anfensi.com' in url:
                    links = re.findall(r'href="(https?://www\.anfensi\.com/down/\d+\.html)"', r.text)
                    if not links:
                        links = re.findall(r'href="(/down/\d+\.html)"', r.text)
                        links = [f'http://www.anfensi.com{l}' for l in links]
                    if links:
                        detail = fetch_anfensi_detail(client, links[0], pkg)
                        if detail:
                            return detail
        except:
            pass
        time.sleep(0.3)
    
    return None


def determine_product_line(pkg):
    """根据包名确定产品线"""
    if 'lark' in pkg:
        return '飞书'
    elif 'rimet' in pkg:
        return '钉钉'
    elif 'taurus' in pkg:
        return '钉钉'
    return '办公协同'


def determine_discovery_method(pkg):
    """根据包名确定发现方法"""
    if 'lark' in pkg:
        return 'search_engine_feishu_custom'
    elif 'rimet' in pkg:
        return 'search_engine_dingding_custom'
    elif 'taurus' in pkg:
        return 'search_engine_taurus_custom'
    return 'search_engine_custom'


def main():
    pkgs = load_inferred_pkgs()
    if not pkgs:
        print("没有找到source_site='包名推断'的记录")
        return
    
    print(f"需要通过搜索引擎获取真实信息的包名: {len(pkgs)} 个")
    
    client = httpx.Client(timeout=20, follow_redirects=True, verify=False, headers=HEADERS)
    db = AppInfoDB()
    
    found_count = 0
    not_found = []
    results = {}  # pkg -> info
    
    for i, (pkg, old_name) in enumerate(pkgs):
        print(f"\n[{i+1}/{len(pkgs)}] 搜索: {pkg} (原名: {old_name})")
        
        info = None
        
        # 1. 搜索引擎 - Bing (加引号精确搜索)
        if not info:
            print("  尝试Bing...", end=" ", flush=True)
            info = search_bing(client, pkg)
            if info:
                print(f"✅ {info['app_name']}")
            else:
                print("❌")
            time.sleep(random.uniform(0.5, 1.0))
        
        # 2. 搜索引擎 - 搜狗
        if not info:
            print("  尝试搜狗...", end=" ", flush=True)
            info = search_sogou(client, pkg)
            if info:
                print(f"✅ {info['app_name']}")
            else:
                print("❌")
            time.sleep(random.uniform(0.5, 1.0))
        
        # 3. 第三方下载站直接搜索
        if not info:
            print("  尝试下载站搜索...", end=" ", flush=True)
            info = try_direct_download_sites(client, pkg)
            if info:
                print(f"✅ {info['app_name']}")
            else:
                print("❌")
            time.sleep(random.uniform(0.3, 0.8))
        
        if info:
            found_count += 1
            results[pkg] = info
            
            pl = determine_product_line(pkg)
            dm = determine_discovery_method(pkg)
            
            # 先删除旧的"包名推断"记录
            conn = sqlite3.connect('output/results.db')
            c = conn.cursor()
            c.execute("DELETE FROM app_info WHERE package_name=? AND source_site='包名推断'", (pkg,))
            conn.commit()
            conn.close()
            
            # 插入新记录
            try:
                ok = db.insert_app(
                    package_name=pkg,
                    app_name=info.get('app_name', ''),
                    product_line=pl,
                    enterprise_name=info.get('enterprise_name', ''),
                    developer=info.get('developer', ''),
                    version=info.get('version', ''),
                    version_code='',
                    update_date='',
                    download_count=info.get('download_count', ''),
                    description=info.get('description', ''),
                    source_site=info.get('source_site', '搜索引擎'),
                    source_url=info.get('source_url', ''),
                    discovery_method=dm,
                )
                if ok:
                    print(f"  ✅ 入库成功: {info['app_name']} ({info.get('source_site', '?')})")
                else:
                    print(f"  ⚠️ 入库失败(可能重复)")
            except Exception as e:
                print(f"  ❌ DB错误: {e}")
        else:
            not_found.append((pkg, old_name))
            print(f"  ℹ️  搜索引擎未找到，保留原记录: {old_name}")
        
        # 请求间隔
        time.sleep(random.uniform(0.5, 1.5))
    
    # === 汇总 ===
    print()
    print("=" * 60)
    print("搜索引擎爬取汇总")
    print("=" * 60)
    print(f"总共: {len(pkgs)} 个包名")
    print(f"搜索引擎找到: {found_count}")
    print(f"未找到(保留原记录): {len(not_found)}")
    
    if results:
        print("\n--- 搜索引擎找到的 ---")
        for pkg, info in results.items():
            print(f"  {pkg} -> {info['app_name']} ({info.get('source_site', '?')})")
    
    if not_found:
        print(f"\n--- 未找到的 {len(not_found)} 个 ---")
        for pkg, old_name in not_found:
            print(f"  {pkg} -> 保留: {old_name}")
    
    # 质量评分和导出
    print("\n执行质量评分和导出...")
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
