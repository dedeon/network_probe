"""
直接爬虫 - 高效获取企业IM/OA/政务应用包信息
策略：
1. 预置大规模已知包名列表（政务App + 办公协同App + 三大产品线相关）
2. 用应用宝详情页批量验证，提取应用信息
3. 用APKPure搜索 + 详情页补充更多应用
4. 用搜索引擎发现更多包名
5. 结果存入SQLite数据库
"""
import httpx
import re
import json
import time
import random
import sqlite3
import os
import sys
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import OUTPUT_DIR, PRODUCT_LINES, RESULTS_DB
from storage.db import AppInfoDB
from utils.logger import setup_logger, get_logger

setup_logger()
logger = get_logger('direct_crawler')

# ============================================================
# 已知应用列表 - 预先整理的目标应用
# ============================================================

# 格式: (包名, 应用名, 产品线, 备注)
# 产品线: '企业微信', '钉钉', '飞书', '办公协同', '政务服务'
KNOWN_APPS = [
    # ===== 企业微信相关 =====
    ('com.tencent.wework', '企业微信', '企业微信', '官方'),
    ('com.tencent.wework.email', '企业微信邮箱', '企业微信', ''),
    
    # ===== 钉钉相关 =====
    ('com.alibaba.android.rimet', '钉钉', '钉钉', '官方'),
    ('com.alibaba.dingtalk.global', 'DingTalk Lite', '钉钉', '国际版'),
    ('com.alibaba.alading', '钉钉Lite', '钉钉', ''),
    
    # ===== 飞书相关 =====
    ('com.ss.android.lark', '飞书', '飞书', '官方'),
    ('com.larksuite.suite', 'Lark', '飞书', '国际版'),
    
    # ===== 腾讯办公协同 =====
    ('com.tencent.docs', '腾讯文档', '企业微信', '腾讯系'),
    ('com.tencent.meeting', '腾讯会议', '企业微信', '腾讯系'),
    ('com.tencent.tim', 'TIM', '企业微信', '腾讯系'),
    ('com.tencent.mobileqq', 'QQ', '企业微信', '腾讯系'),
    ('com.tencent.mm', '微信', '企业微信', '腾讯系'),
    ('com.tencent.txcloud', '腾讯云', '企业微信', '腾讯系'),
    
    # ===== 阿里办公协同 =====
    ('com.alibaba.teambition', 'Teambition', '钉钉', '阿里系'),
    ('com.alibaba.aliyun', '阿里云', '钉钉', '阿里系'),
    ('com.taobao.taobao', '淘宝', '钉钉', '阿里系'),
    
    # ===== 字节跳动办公 =====
    ('com.bytedance.ee.lark', '飞书国际版', '飞书', '字节系'),
    ('com.ss.android.article.news', '今日头条', '飞书', '字节系'),
    
    # ===== 华为办公 =====
    ('com.huawei.works', 'WeLink', '办公协同', '华为'),
    ('com.huawei.welink', '华为WeLink', '办公协同', '华为'),
    ('com.huawei.cloud.app', '华为云', '办公协同', '华为'),
    
    # ===== 传统OA/办公软件 =====
    ('cn.wps.moffice_eng', 'WPS Office', '办公协同', 'WPS'),
    ('cn.wps.moffice_i18n', 'WPS International', '办公协同', 'WPS'),
    ('com.kingsoft.office.pro', 'WPS专业版', '办公协同', 'WPS'),
    ('com.seeyon.cmp', '致远M3', '办公协同', '致远互联'),
    ('com.seeyon.a8plus', '致远A8+', '办公协同', '致远互联'),
    ('com.seeyon.apps', '致远互联', '办公协同', '致远互联'),
    ('com.weaver.emobile', '泛微eMobile', '办公协同', '泛微'),
    ('com.weaver.emobile7', '泛微eMobile7', '办公协同', '泛微'),
    ('com.weaver.eteams', '泛微eTeams', '办公协同', '泛微'),
    ('com.landray.ekp.mobile', '蓝凌移动办公', '办公协同', '蓝凌'),
    ('com.landray.app', '蓝凌OA', '办公协同', '蓝凌'),
    ('com.tongda.oaapp', '通达OA', '办公协同', '通达'),
    ('com.tongda.oa', '通达信科OA', '办公协同', '通达'),
    ('com.yonyou.yht', '友户通', '办公协同', '用友'),
    ('com.yonyou.nccm', '用友NC', '办公协同', '用友'),
    ('com.yonyou.ump', '用友移动平台', '办公协同', '用友'),
    ('com.kingdee.yunzhijia', '云之家', '办公协同', '金蝶'),
    ('com.kingdee.eas.phone', '金蝶EAS', '办公协同', '金蝶'),
    ('com.chanjet.worktogether', '畅捷通工作圈', '办公协同', '畅捷通'),
    ('com.inspur.emmcloud', '浪潮云+', '办公协同', '浪潮'),
    ('com.inspur.oa', '浪潮OA', '办公协同', '浪潮'),
    
    # ===== 国际办公应用 =====
    ('com.microsoft.teams', 'Microsoft Teams', '办公协同', '微软'),
    ('com.microsoft.office.outlook', 'Outlook', '办公协同', '微软'),
    ('com.microsoft.skydrive', 'OneDrive', '办公协同', '微软'),
    ('com.microsoft.office.officehubrow', 'Microsoft 365', '办公协同', '微软'),
    ('com.microsoft.office.word', 'Word', '办公协同', '微软'),
    ('com.microsoft.office.excel', 'Excel', '办公协同', '微软'),
    ('com.microsoft.office.powerpoint', 'PowerPoint', '办公协同', '微软'),
    ('com.slack', 'Slack', '办公协同', 'Slack'),
    ('com.Slack', 'Slack', '办公协同', 'Slack'),
    ('com.google.android.apps.docs', 'Google Drive', '办公协同', 'Google'),
    ('com.google.android.apps.meetings', 'Google Meet', '办公协同', 'Google'),
    ('com.google.android.gm', 'Gmail', '办公协同', 'Google'),
    ('us.zoom.videomeetings', 'Zoom', '办公协同', 'Zoom'),
    ('com.facebook.work', 'Workplace', '办公协同', 'Meta'),
    ('com.zoho.workplace', 'Zoho Workplace', '办公协同', 'Zoho'),
    ('com.atlassian.android.jira.core', 'Jira', '办公协同', 'Atlassian'),
    ('com.trello', 'Trello', '办公协同', 'Atlassian'),
    ('com.basecamp.bc3', 'Basecamp', '办公协同', 'Basecamp'),
    ('com.notion.id', 'Notion', '办公协同', 'Notion'),
    
    # ===== 各省政务服务App =====
    ('com.hanweb.android.zhejiang.activity', '浙里办', '政务服务', '浙江'),
    ('cn.gov.zj.ztzwfw', '浙里办(备用)', '政务服务', '浙江'),
    ('com.hundsun.zjzwfw', '浙政钉', '钉钉', '浙江政务'),
    ('cn.gov.gd.govba', '粤省事', '政务服务', '广东'),
    ('cn.gov.gd.ydzy', '粤政易', '政务服务', '广东'),
    ('com.gdga.gdrjz', '粤居码', '政务服务', '广东'),
    ('cn.gov.sh.ssb', '随申办', '政务服务', '上海'),
    ('cn.gov.sh.zwdts', '随申办市民云', '政务服务', '上海'),
    ('cn.gov.ah.zzfw', '皖事通', '政务服务', '安徽'),
    ('cn.gov.jx.zwtb', '赣服通', '政务服务', '江西'),
    ('cn.gov.fj.mzfw', '闽政通', '政务服务', '福建'),
    ('cn.gov.fujian.mzfw', '闽政通(备用)', '政务服务', '福建'),
    ('cn.gov.henan.yuspeed', '豫事办', '政务服务', '河南'),
    ('cn.gov.hubei.ehb', '鄂汇办', '政务服务', '湖北'),
    ('cn.gov.hunan.xzsp', '新湘事成', '政务服务', '湖南'),
    ('cn.gov.heb.jsb', '冀时办', '政务服务', '河北'),
    ('cn.gov.sx.sjt', '三晋通', '政务服务', '山西'),
    ('cn.gov.jl.jsb', '吉事办', '政务服务', '吉林'),
    ('cn.gov.liaoning.lst', '辽事通', '政务服务', '辽宁'),
    ('cn.gov.nmg.msb', '蒙速办', '政务服务', '内蒙古'),
    ('cn.gov.sd.asd', '爱山东', '政务服务', '山东'),
    ('cn.gov.js.sfb', '苏服办', '政务服务', '江苏'),
    ('cn.gov.sc.tfzwt', '天府通办', '政务服务', '四川'),
    ('cn.gov.cq.ykb', '渝快办', '政务服务', '重庆'),
    ('cn.gov.bj.bjt', '北京通', '政务服务', '北京'),
    ('cn.gov.tj.txb', '津心办', '政务服务', '天津'),
    ('cn.gov.hain.hyb', '海易办', '政务服务', '海南'),
    ('cn.gov.gx.zgz', '壮掌桂', '政务服务', '广西'),
    ('cn.gov.gz.ysdcb', '贵人服务', '政务服务', '贵州'),
    ('cn.gov.yn.ysb', '云上办', '政务服务', '云南'),
    ('cn.gov.xz.xzzw', '西藏政务', '政务服务', '西藏'),
    ('cn.gov.sx.szht', '陕政通', '政务服务', '陕西'),
    ('cn.gov.gs.gkb', '甘快办', '政务服务', '甘肃'),
    ('cn.gov.qh.qsb', '青松办', '政务服务', '青海'),
    ('cn.gov.nx.wdnx', '我的宁夏', '政务服务', '宁夏'),
    ('cn.gov.xj.xjzw', '新疆政务', '政务服务', '新疆'),
    
    # ===== 企业银行/金融办公 =====
    ('com.icbc', '工商银行', '办公协同', '银行'),
    ('com.chinamworld.bocmbci', '中国银行', '办公协同', '银行'),
    ('com.ecitic.bank.mobile', '中信银行', '办公协同', '银行'),
    ('com.cmb.pb', '招商银行', '办公协同', '银行'),
    ('com.pingan.papd', '平安金管家', '办公协同', '保险'),
    ('com.chinamworld.klb', '昆仑银行', '办公协同', '银行'),
    
    # ===== 低代码/无代码平台 =====
    ('com.mingdao.app', '明道云', '办公协同', '低代码'),
    ('cn.teambition.agile', '飞项', '钉钉', '效率'),
    ('com.worktile.im', 'Worktile', '办公协同', '项目管理'),
    ('com.ones.project', 'ONES', '办公协同', '项目管理'),
    ('com.tower.app', 'Tower', '办公协同', '项目管理'),
    
    # ===== 即时通讯/协作 =====
    ('com.cisco.webex.meetings', 'Webex Meetings', '办公协同', 'Cisco'),
    ('com.ringcentral.android', 'RingCentral', '办公协同', '通讯'),
    ('com.duowan.yy', 'YY', '办公协同', 'YY'),
    ('com.netease.mail', '网易邮箱大师', '办公协同', '网易'),
    ('com.netease.popo', 'POPO', '办公协同', '网易'),
    ('com.foxmail', 'Foxmail', '企业微信', '腾讯系'),
    ('com.tencent.qqmail', 'QQ邮箱', '企业微信', '腾讯系'),
    ('com.alibaba.wireless.ichangmessenger', '千牛', '钉钉', '阿里系'),
    ('com.alibaba.alinspire', '灵犀', '钉钉', '阿里系'),
    
    # ===== 招聘/HR =====
    ('com.zhaopin.social', '智联招聘', '办公协同', 'HR'),
    ('com.nowcoder.app.florida', '牛客', '办公协同', 'HR'),
    ('com.linkedin.android', 'LinkedIn', '办公协同', 'HR'),
    
    # ===== 文档/笔记 =====
    ('com.yinxiang', '印象笔记', '办公协同', '笔记'),
    ('com.evernote', 'Evernote', '办公协同', '笔记'),
    ('com.shimo.app', '石墨文档', '办公协同', '文档'),
    ('cn.yuque.app', '语雀', '钉钉', '阿里系'),
    ('com.jideos.jnote', '锤子便签', '办公协同', '笔记'),
]


class DirectCrawler:
    """直接爬虫 - 高效批量获取应用信息"""
    
    def __init__(self):
        self.db = AppInfoDB()
        self.client = httpx.Client(
            timeout=20, follow_redirects=True, verify=False,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        self.stats = {
            'yingyongbao_found': 0,
            'yingyongbao_failed': 0,
            'apkpure_found': 0,
            'search_found': 0,
            'total_saved': 0,
        }
    
    def run(self):
        """执行完整的爬取流程"""
        logger.info("=" * 60)
        logger.info("直接爬虫 - 开始执行")
        logger.info(f"已知应用列表: {len(KNOWN_APPS)} 个")
        logger.info("=" * 60)
        
        # 清理旧数据（重新开始）
        self._clean_old_data()
        
        # 阶段1：用应用宝详情页批量验证已知包名
        logger.info("\n阶段1: 应用宝详情页批量验证")
        logger.info("-" * 40)
        self._phase1_yingyongbao_verify()
        
        # 阶段2：用APKPure搜索发现更多应用
        logger.info("\n阶段2: APKPure搜索补充")
        logger.info("-" * 40)
        self._phase2_apkpure_search()
        
        # 阶段3：搜索引擎发现更多包名
        logger.info("\n阶段3: 搜索引擎补充")
        logger.info("-" * 40)
        self._phase3_search_engine()
        
        # 汇总
        total = self.db.count()
        logger.info("\n" + "=" * 60)
        logger.info(f"爬取完成！总计 {total} 条应用记录")
        logger.info(f"  应用宝发现: {self.stats['yingyongbao_found']}")
        logger.info(f"  APKPure发现: {self.stats['apkpure_found']}")
        logger.info(f"  搜索引擎发现: {self.stats['search_found']}")
        logger.info(f"  保存成功: {self.stats['total_saved']}")
        logger.info("=" * 60)
        
        return total
    
    def _clean_old_data(self):
        """清理旧的结果数据"""
        try:
            conn = self.db._get_conn()
            conn.execute('DELETE FROM app_info')
            conn.commit()
            logger.info("已清理旧数据")
        except Exception as e:
            logger.error(f"清理旧数据失败: {e}")
    
    def _phase1_yingyongbao_verify(self):
        """阶段1：用应用宝详情页批量验证"""
        total_found = 0
        
        for i, (pkg, name, product_line, note) in enumerate(KNOWN_APPS):
            if i > 0 and i % 20 == 0:
                logger.info(f"  进度: {i}/{len(KNOWN_APPS)}, 已发现 {total_found}")
            
            info = self._fetch_yingyongbao_detail(pkg)
            if info:
                # 补充已知信息
                if not info.get('product_line'):
                    info['product_line'] = product_line
                info['note'] = note
                
                if self._save_app(info, source='应用宝', method='known_package_verify'):
                    total_found += 1
                    self.stats['yingyongbao_found'] += 1
            else:
                self.stats['yingyongbao_failed'] += 1
            
            time.sleep(random.uniform(0.3, 0.8))
        
        logger.info(f"阶段1完成: 应用宝验证成功 {total_found}/{len(KNOWN_APPS)}")
    
    def _phase2_apkpure_search(self):
        """阶段2：用APKPure搜索补充"""
        search_keywords = [
            'wework', 'dingtalk', 'lark', 'wecom',
            'enterprise wechat', 'feishu', 'alibaba office',
            '企业微信', '钉钉', '飞书',
            'mobile office china', 'government app china',
            'OA office', 'collaboration app',
            'tencent meeting', 'tencent docs',
        ]
        
        existing_pkgs = self.db.get_package_names()
        new_found = 0
        
        for kw in search_keywords:
            pkgs = self._search_apkpure(kw)
            for pkg, name, url in pkgs:
                if pkg in existing_pkgs:
                    continue
                
                # 先在应用宝验证
                info = self._fetch_yingyongbao_detail(pkg)
                if info:
                    product_line = self._match_product_line(pkg, info.get('app_name', name))
                    if product_line:
                        info['product_line'] = product_line
                        if self._save_app(info, source='应用宝', method='apkpure_discover'):
                            new_found += 1
                            self.stats['apkpure_found'] += 1
                            existing_pkgs.add(pkg)
                else:
                    # 直接用APKPure信息
                    product_line = self._match_product_line(pkg, name)
                    if product_line:
                        app_info = {
                            'package_name': pkg,
                            'app_name': name,
                            'product_line': product_line,
                            'url': url,
                        }
                        if self._save_app(app_info, source='APKPure', method='apkpure_search'):
                            new_found += 1
                            self.stats['apkpure_found'] += 1
                            existing_pkgs.add(pkg)
                
                time.sleep(random.uniform(0.5, 1.0))
            
            time.sleep(random.uniform(3, 5))
        
        logger.info(f"阶段2完成: APKPure新发现 {new_found} 个应用")
    
    def _phase3_search_engine(self):
        """阶段3：搜索引擎发现更多包名"""
        search_queries = [
            '"com.tencent.wework" 定制版 企业',
            '"com.alibaba.android.rimet" 专属版',
            '"政务钉钉" android apk 包名',
            '"浙政钉" android 包名 com.',
            '"粤省事" 包名 android',
            '"皖事通" android package',
            '"随申办" android 包名',
            '"闽政通" package android',
            '"云之家" android 包名',
            '"泛微" emobile android 包名',
            '"致远" seeyon android 包名',
            '政务App android 包名 列表 2025',
            '企业OA mobile android package name',
        ]
        
        existing_pkgs = self.db.get_package_names()
        new_found = 0
        
        for query in search_queries:
            pkgs = self._search_bing_for_packages(query)
            for pkg in pkgs:
                if pkg in existing_pkgs:
                    continue
                
                # 在应用宝验证
                info = self._fetch_yingyongbao_detail(pkg)
                if info:
                    product_line = self._match_product_line(pkg, info.get('app_name', ''))
                    if product_line:
                        info['product_line'] = product_line
                        if self._save_app(info, source='应用宝', method='search_engine_discover'):
                            new_found += 1
                            self.stats['search_found'] += 1
                            existing_pkgs.add(pkg)
                
                time.sleep(random.uniform(0.3, 0.8))
            
            time.sleep(random.uniform(2, 4))
        
        logger.info(f"阶段3完成: 搜索引擎新发现 {new_found} 个应用")
    
    # ============================================================
    # 数据源方法
    # ============================================================
    
    def _fetch_yingyongbao_detail(self, package_name: str) -> Optional[dict]:
        """从应用宝详情页获取应用信息"""
        url = f'https://sj.qq.com/appdetail/{package_name}'
        try:
            resp = self.client.get(url)
            if resp.status_code != 200 or len(resp.text) < 2000:
                return None
            
            soup = BeautifulSoup(resp.text, 'lxml')
            title = soup.select_one('title')
            tt = title.get_text(strip=True) if title else ''
            
            if '找不到' in tt or '404' in tt or len(tt) < 5:
                return None
            
            info = {'package_name': package_name, 'url': url}
            
            # 提取应用名
            app_name = tt.split('app')[0].strip()
            if not app_name or app_name == '应用宝' or len(app_name) < 2:
                app_name = tt.split('下载')[0].strip()
            if not app_name or app_name == '应用宝':
                app_name = tt.split('官方')[0].strip()
            if app_name and '应用宝' not in app_name:
                # 清理名称
                app_name = re.sub(r'(官方版|最新版|安卓版|手机版).*$', '', app_name).strip()
                app_name = re.sub(r'-.*$', '', app_name).strip()
                info['app_name'] = app_name
            
            # 从meta提取描述
            for meta in soup.find_all('meta'):
                name = meta.get('name', '') or meta.get('property', '')
                content = meta.get('content', '')
                if 'description' in name.lower() and content:
                    info['description'] = content[:500]
                    break
            
            # 从__NEXT_DATA__提取更多信息
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
                            if isinstance(cd, dict):
                                if cd.get('appName') and not info.get('app_name'):
                                    info['app_name'] = cd['appName']
                                if cd.get('authorName') and not info.get('developer'):
                                    info['developer'] = cd['authorName']
                                if cd.get('versionName') and not info.get('version'):
                                    info['version'] = cd['versionName']
                                if cd.get('appDownCount') and not info.get('download_count'):
                                    info['download_count'] = str(cd['appDownCount'])
                                if cd.get('description') and not info.get('description'):
                                    info['description'] = cd['description'][:500]
                except:
                    pass
            
            if not info.get('app_name'):
                return None
            
            return info
            
        except Exception as e:
            logger.debug(f"应用宝获取失败 {package_name}: {e}")
            return None
    
    def _search_apkpure(self, keyword: str) -> list[tuple]:
        """从APKPure搜索，返回(包名, 应用名, URL)列表"""
        results = []
        try:
            resp = self.client.get(f'https://apkpure.com/cn/search?q={keyword}')
            if resp.status_code != 200:
                return results
            
            # 从URL中提取包名
            for m in re.finditer(
                r'/(cn/)?[^/]+/((?:com|cn|org|io|net)\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z0-9_]+)+)',
                resp.text
            ):
                pkg = m.group(2)
                skip = ['com.google.android', 'com.android.', 'com.apkpure']
                if any(pkg.startswith(s) for s in skip):
                    continue
                
                # 获取应用名（从搜索结果页面难以精确提取，先用包名）
                results.append((pkg, pkg, f'https://apkpure.com/cn/app/{pkg}'))
            
            # 去重
            seen = set()
            unique = []
            for pkg, name, url in results:
                if pkg not in seen:
                    seen.add(pkg)
                    unique.append((pkg, name, url))
            
            if unique:
                logger.info(f"  APKPure搜索 '{keyword}': 发现 {len(unique)} 个包名")
            return unique
            
        except Exception as e:
            logger.debug(f"APKPure搜索失败 '{keyword}': {e}")
            return results
    
    def _search_bing_for_packages(self, query: str) -> list[str]:
        """从必应搜索结果中提取Android包名"""
        packages = []
        try:
            resp = self.client.get('https://cn.bing.com/search', params={'q': query, 'count': 20})
            if resp.status_code != 200:
                return packages
            
            # 提取所有可能的包名
            text = resp.text
            patterns = [
                r'\b(com\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9_]*){1,5})\b',
                r'\b(cn\.gov\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9_]*){1,4})\b',
                r'\b(cn\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9_]*){1,5})\b',
                r'\b(org\.[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9_]*){1,5})\b',
            ]
            
            all_pkgs = set()
            for pat in patterns:
                for m in re.finditer(pat, text):
                    all_pkgs.add(m.group(1))
            
            # 过滤掉明显不是应用包名的
            skip_prefixes = [
                'com.google.', 'com.microsoft.bing', 'com.android.',
                'cn.bing.', 'com.bing.', 'com.sogou.',
                'com.baidu.searchbox',
            ]
            skip_suffixes = ['.com', '.cn', '.net', '.org', '.html', '.js', '.css']
            
            for pkg in all_pkgs:
                if any(pkg.startswith(s) for s in skip_prefixes):
                    continue
                if any(pkg.endswith(s) for s in skip_suffixes):
                    continue
                if len(pkg.split('.')) < 3:
                    continue
                packages.append(pkg)
            
            packages = list(set(packages))
            if packages:
                logger.info(f"  必应搜索发现 {len(packages)} 个候选包名")
            return packages
            
        except Exception as e:
            logger.debug(f"必应搜索失败: {e}")
            return packages
    
    # ============================================================
    # 保存和匹配方法
    # ============================================================
    
    def _save_app(self, app_info: dict, source: str, method: str) -> bool:
        """保存应用到数据库"""
        pkg = app_info.get('package_name', '')
        name = app_info.get('app_name', '')
        pl = app_info.get('product_line', '')
        
        if not pkg or not name:
            return False
        
        # 如果没有产品线，尝试匹配
        if not pl:
            pl = self._match_product_line(pkg, name)
        
        if not pl:
            pl = '办公协同'  # 默认分类
        
        try:
            result = self.db.insert_app(
                package_name=pkg,
                app_name=name,
                product_line=pl,
                enterprise_name=app_info.get('enterprise_name', ''),
                developer=app_info.get('developer', ''),
                version=app_info.get('version', ''),
                version_code=app_info.get('version_code', ''),
                update_date=app_info.get('update_date', ''),
                download_count=app_info.get('download_count', ''),
                description=app_info.get('description', '')[:500],
                source_site=source,
                source_url=app_info.get('url', ''),
                discovery_method=method,
            )
            if result:
                self.stats['total_saved'] += 1
                logger.info(f"    ✓ {pkg:45s} | {name[:20]:20s} | {pl}")
            return result
        except Exception as e:
            logger.debug(f"保存失败 {pkg}: {e}")
            return False
    
    def _match_product_line(self, pkg: str, name: str) -> str:
        """匹配产品线"""
        pkg_lower = pkg.lower()
        name_lower = name.lower() if name else ''
        
        # 企业微信
        if any(kw in pkg_lower for kw in ['wework', 'wecom', 'tencent.wework']):
            return '企业微信'
        if any(kw in name_lower for kw in ['企业微信', '企微', 'wework', 'wecom']):
            return '企业微信'
        
        # 钉钉
        if any(kw in pkg_lower for kw in ['rimet', 'dingtalk', 'alibaba.android.rimet']):
            return '钉钉'
        if any(kw in name_lower for kw in ['钉钉', 'dingtalk', '政务钉']):
            return '钉钉'
        
        # 飞书
        if any(kw in pkg_lower for kw in ['lark', 'feishu', 'ss.android.lark']):
            return '飞书'
        if any(kw in name_lower for kw in ['飞书', 'lark', 'feishu']):
            return '飞书'
        
        # 腾讯系 → 企业微信
        if 'com.tencent.' in pkg_lower:
            return '企业微信'
        
        # 阿里系 → 钉钉
        if 'com.alibaba.' in pkg_lower:
            return '钉钉'
        
        # 字节系 → 飞书
        if any(kw in pkg_lower for kw in ['com.ss.android', 'com.bytedance']):
            return '飞书'
        
        # 政务
        if 'cn.gov.' in pkg_lower or any(kw in name_lower for kw in ['政务', '政通', '省事', '事通', '事办', '办事']):
            return '政务服务'
        
        return ''
    
    def close(self):
        self.client.close()
        self.db.close()


def main():
    """主函数"""
    crawler = DirectCrawler()
    try:
        total = crawler.run()
        
        # 如果结果数据够多，运行pipeline和导出
        if total > 0:
            logger.info("\n开始数据处理和导出...")
            from storage.db import CustomerDB
            from storage.exporter import DataExporter
            
            # 简单的数据处理
            from pipeline.quality_scorer import QualityScorer
            scorer = QualityScorer(crawler.db)
            scorer.run()
            
            # 导出
            customer_db = CustomerDB()
            exporter = DataExporter(customer_db, crawler.db)
            paths = exporter.export_all()
            
            for name, path in paths.items():
                logger.info(f"已导出: {name} → {path}")
            
            exporter.print_summary()
            customer_db.close()
    finally:
        crawler.close()


if __name__ == '__main__':
    main()
