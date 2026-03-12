"""直接爬虫v2 - 修复解析+滚雪球"""
import httpx, re, json, time, random, os, sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from storage.db import AppInfoDB
from utils.logger import setup_logger, get_logger

setup_logger()
logger = get_logger('direct_crawler')

KNOWN_APPS = [
    ('com.tencent.wework','企业微信','企业微信'),
    ('com.tencent.docs','企业微信','腾讯文档'),
    ('com.tencent.tim','企业微信','TIM'),
    ('com.tencent.mobileqq','企业微信','QQ'),
    ('com.tencent.mm','企业微信','微信'),
    ('com.tencent.qqmail','企业微信','QQ邮箱'),
    ('com.tencent.map','企业微信','腾讯地图'),
    ('com.tencent.qqlive','企业微信','腾讯视频'),
    ('com.tencent.qqmusic','企业微信','QQ音乐'),
    ('com.tencent.karaoke','企业微信','全民K歌'),
    ('com.tencent.weishi','企业微信','微视'),
    ('com.tencent.news','企业微信','腾讯新闻'),
    ('com.tencent.mtt','企业微信','QQ浏览器'),
    ('com.tencent.androidqqmanager','企业微信','手机管家'),
    ('com.tencent.wetype','企业微信','微信输入法'),
    ('com.tencent.reading','企业微信','QQ阅读'),
    ('com.alibaba.android.rimet','钉钉','钉钉'),
    ('com.alibaba.aliyun','钉钉','阿里云'),
    ('com.taobao.taobao','钉钉','淘宝'),
    ('com.eg.android.AlipayGphone','钉钉','支付宝'),
    ('com.taobao.idlefish','钉钉','闲鱼'),
    ('com.alibaba.wireless.ichangmessenger','钉钉','千牛'),
    ('com.tmall.wireless','钉钉','天猫'),
    ('com.UCMobile','钉钉','UC浏览器'),
    ('com.autonavi.minimap','钉钉','高德地图'),
    ('com.youku.phone','钉钉','优酷'),
    ('com.taobao.trip','钉钉','飞猪'),
    ('com.cainiao.wireless.homepage','钉钉','菜鸟'),
    ('com.alibaba.teambition','钉钉','Teambition'),
    ('com.ss.android.lark','飞书','飞书'),
    ('com.ss.android.article.news','飞书','今日头条'),
    ('com.ss.android.ugc.aweme','飞书','抖音'),
    ('com.ss.android.ugc.aweme.lite','飞书','抖音极速版'),
    ('com.ss.android.article.lite','飞书','头条极速版'),
    ('com.ss.android.ugc.live','飞书','抖音火山版'),
    ('com.ss.android.auto','飞书','懂车帝'),
    ('com.ss.android.article.video','飞书','西瓜视频'),
    ('com.luna.music','飞书','汽水音乐'),
    ('cn.wps.moffice_eng','办公协同','WPS Office'),
    ('cn.wps.yun','办公协同','WPS云办公'),
    ('com.huawei.welink','办公协同','华为WeLink'),
    ('com.seeyon.cmp','办公协同','致远M3'),
    ('com.weaver.emobile7','办公协同','泛微eMobile7'),
    ('com.inspur.emmcloud','办公协同','浪潮云+'),
    ('com.microsoft.teams','办公协同','Teams'),
    ('com.microsoft.office.outlook','办公协同','Outlook'),
    ('com.microsoft.skydrive','办公协同','OneDrive'),
    ('com.microsoft.office.word','办公协同','Word'),
    ('com.microsoft.office.excel','办公协同','Excel'),
    ('com.microsoft.office.powerpoint','办公协同','PPT'),
    ('com.microsoft.office.onenote','办公协同','OneNote'),
    ('com.icbc','办公协同','工商银行'),
    ('com.chinamworld.bocmbci','办公协同','中国银行'),
    ('com.ecitic.bank.mobile','办公协同','中信银行'),
    ('cmb.pb','办公协同','招商银行'),
    ('com.chinamworld.main','办公协同','建设银行'),
    ('com.android.bankabc','办公协同','农业银行'),
    ('com.bankcomm.Bankcomm','办公协同','交通银行'),
    ('com.pingan.papd','办公协同','平安金管家'),
    ('com.yitong.mbank.psbc','办公协同','邮储银行'),
    ('com.spdb.mobilebankN','办公协同','浦发银行'),
    ('com.cib.cibmb','办公协同','兴业银行'),
    ('com.netease.mail','办公协同','网易邮箱大师'),
    ('com.zhaopin.social','办公协同','智联招聘'),
    ('com.nowcoder.app.florida','办公协同','牛客'),
    ('com.hpbr.bosszhipin','办公协同','BOSS直聘'),
    ('com.yinxiang','办公协同','印象笔记'),
    ('com.youdao.note','办公协同','有道云笔记'),
    ('com.baidu.netdisk','办公协同','百度网盘'),
    ('com.hanweb.android.zhejiang.activity','政务服务','浙里办'),
    ('com.sina.weibo','办公协同','微博'),
    ('com.zhihu.android','办公协同','知乎'),
    ('tv.danmaku.bili','办公协同','哔哩哔哩'),
    ('com.xingin.xhs','办公协同','小红书'),
    ('com.baidu.searchbox','办公协同','百度'),
    ('com.baidu.BaiduMap','办公协同','百度地图'),
    ('com.baidu.input','办公协同','百度输入法'),
    ('com.iflytek.inputmethod','办公协同','讯飞输入法'),
    ('com.sdu.didi.psnger','办公协同','滴滴出行'),
    ('ctrip.android.view','办公协同','携程'),
    ('com.MobileTicket','办公协同','12306'),
    ('com.netease.cloudmusic','办公协同','网易云音乐'),
    ('com.kuaishou.nebula','办公协同','快手'),
    ('com.jingdong.app.mall','办公协同','京东'),
    ('com.xunmeng.pinduoduo','办公协同','拼多多'),
    ('com.meituan','办公协同','美团'),
    ('com.dianping.v1','办公协同','大众点评'),
    ('com.qiyi.video','办公协同','爱奇艺'),
    ('com.kugou.android','办公协同','酷狗音乐'),
    ('com.ximalaya.ting.android','办公协同','喜马拉雅'),
    ('com.todesk','办公协同','ToDesk'),
    ('com.oray.sunlogin','办公协同','向日葵'),
    ('com.eastmoney.android.berlin','办公协同','东方财富'),
    ('com.hexin.plat.android','办公协同','同花顺'),
    ('com.sf.activity','办公协同','顺丰速运'),
    ('com.xunlei.downloadprovider','办公协同','迅雷'),
    ('com.cubic.autohome','办公协同','汽车之家'),
    ('com.fenbi.android.servant','办公协同','粉笔'),
    ('com.chaoxing.mobile','办公协同','学习通'),
    ('com.youdao.dict','办公协同','有道词典'),
    ('us.zoom.videomeetings','办公协同','Zoom'),
    ('com.hunantv.imgo.activity','办公协同','芒果TV'),
    ('com.gotokeep.keep','办公协同','Keep'),
    ('com.chinaums.pmp','办公协同','云闪付'),
]


class DirectCrawlerV2:
    def __init__(self):
        self.db = AppInfoDB()
        self.client = httpx.Client(
            timeout=20, follow_redirects=True, verify=False,
            headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36','Accept-Language':'zh-CN,zh;q=0.9'})
        self.found_pkgs = set()
        self.checked_pkgs = set()
        self.discovered_pkgs = []
        self.stats = {'found':0,'checked':0,'from_known':0,'from_recommend':0}

    def run(self):
        logger.info("="*60)
        logger.info(f"直接爬虫v2, 已知应用: {len(KNOWN_APPS)}")
        logger.info("="*60)
        self._clean()
        logger.info("\n阶段1: 验证已知包名")
        self._phase1()
        logger.info("\n阶段2: 推荐滚雪球")
        self._phase2()
        total = self.db.count()
        logger.info(f"\n完成! 总计{total}条, 已知{self.stats['from_known']}, 滚雪球{self.stats['from_recommend']}, 检查{self.stats['checked']}")
        return total

    def _clean(self):
        try:
            conn = self.db._get_conn()
            conn.execute('DELETE FROM app_info')
            conn.commit()
            logger.info("已清理旧数据")
        except: pass

    def _phase1(self):
        for i,(pkg,pl,note) in enumerate(KNOWN_APPS):
            if pkg in self.checked_pkgs: continue
            if i>0 and i%20==0:
                logger.info(f"  进度: {i}/{len(KNOWN_APPS)}, 发现{self.stats['from_known']}")
            info = self._fetch(pkg)
            if info:
                info['product_line'] = pl
                if self._save(info): self.stats['from_known'] += 1
            self.checked_pkgs.add(pkg)
            self.stats['checked'] += 1
            time.sleep(random.uniform(0.15,0.4))
        logger.info(f"阶段1完成: {self.stats['from_known']}/{len(KNOWN_APPS)}")

    def _phase2(self):
        for rnd in range(1,4):
            batch = list(set(self.discovered_pkgs))
            self.discovered_pkgs = []
            new = [p for p in batch if p not in self.checked_pkgs]
            if not new: break
            logger.info(f"  第{rnd}轮: {len(new)}个候选")
            rf = 0
            for i,pkg in enumerate(new):
                if pkg in self.checked_pkgs: continue
                if i>0 and i%30==0:
                    logger.info(f"    进度{i}/{len(new)}, +{rf}")
                info = self._fetch(pkg)
                if info:
                    info['product_line'] = self._match_pl(pkg, info.get('app_name',''))
                    if self._save(info):
                        self.stats['from_recommend'] += 1
                        rf += 1
                self.checked_pkgs.add(pkg)
                self.stats['checked'] += 1
                time.sleep(random.uniform(0.15,0.4))
            logger.info(f"  第{rnd}轮: +{rf}, 总{self.stats['found']}")

    def _fetch(self, pkg):
        url = f'https://sj.qq.com/appdetail/{pkg}'
        try:
            resp = self.client.get(url)
            if resp.status_code != 200 or len(resp.text) < 2000: return None
            info = {'package_name':pkg,'url':url}
            nd = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',resp.text,re.DOTALL)
            if nd:
                try:
                    d = json.loads(nd.group(1))
                    pp = d.get('props',{}).get('pageProps',{})
                    dcr = pp.get('dynamicCardResponse',{}).get('data',{})
                    if isinstance(dcr,dict):
                        for comp in dcr.get('components',[]):
                            cd = comp.get('data',{})
                            if not isinstance(cd,dict): continue
                            if cd.get('name')=='GameDetail':
                                items = cd.get('itemData',[])
                                if isinstance(items,str): items=json.loads(items)
                                if isinstance(items,list) and items:
                                    it = items[0]
                                    if it.get('name'): info['app_name']=it['name']
                                    if it.get('developer'): info['developer']=it['developer']
                                    if it.get('version_name'): info['version']=it['version_name']
                                    if it.get('download_num'): info['download_count']=str(it['download_num'])
                                    if it.get('description'): info['description']=str(it['description'])[:500]
                                    if it.get('operator'): info['enterprise_name']=it['operator']
                            if cd.get('name') in ('YouMayAlsoLike','SameDeveloper'):
                                its = cd.get('itemData',[])
                                if isinstance(its,str): its=json.loads(its)
                                if isinstance(its,list):
                                    for x in its:
                                        if isinstance(x,dict) and x.get('pkg_name'):
                                            self.discovered_pkgs.append(x['pkg_name'])
                    seo = pp.get('seoMeta',{})
                    if not info.get('app_name') and seo.get('title'):
                        info['app_name'] = self._ptitle(seo['title'])
                    if not info.get('description') and seo.get('description'):
                        info['description'] = seo['description'][:500]
                except: pass
            if not info.get('app_name'):
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text,'lxml')
                t = soup.select_one('title')
                if t:
                    tt = t.get_text(strip=True)
                    if '找不到' in tt or '404' in tt: return None
                    info['app_name'] = self._ptitle(tt)
            return info if info.get('app_name') else None
        except: return None

    def _ptitle(self, title):
        if not title: return None
        n = re.sub(r'-应用宝.*$','',title).strip()
        if '-' in n: n=n.split('-')[0].strip()
        n = re.sub(r'(app|APP|App).*$','',n).strip()
        n = re.sub(r'(官方|官网|免费|最新|下载|安装|正版|版本).*$','',n).strip()
        return n if n and len(n)>=1 and '应用宝' not in n else None

    def _save(self, info):
        pkg=info.get('package_name','')
        name=info.get('app_name','')
        pl=info.get('product_line','办公协同')
        if not pkg or not name or pkg in self.found_pkgs: return False
        try:
            r = self.db.insert_app(package_name=pkg,app_name=name,product_line=pl,
                enterprise_name=info.get('enterprise_name',''),developer=info.get('developer',''),
                version=info.get('version',''),version_code='',update_date='',
                download_count=info.get('download_count',''),description=info.get('description',''),
                source_site='应用宝',source_url=info.get('url',''),discovery_method='yingyongbao_v2')
            if r:
                self.found_pkgs.add(pkg)
                self.stats['found'] += 1
                logger.info(f"    ✓ {pkg:45s} | {name[:20]:20s} | {pl}")
            return r
        except: return False

    def _match_pl(self,pkg,name):
        p=pkg.lower(); n=(name or'').lower()
        if 'tencent' in p: return '企业微信'
        if any(k in p for k in ['alibaba','taobao','alipay','rimet','dingtalk','autonavi','youku','cainiao','tmall','ucmobile']): return '钉钉'
        if any(k in p for k in ['ss.android','bytedance','lark','luna.music']): return '飞书'
        if any(k in n for k in ['企业微信','wework']): return '企业微信'
        if any(k in n for k in ['钉钉','dingtalk']): return '钉钉'
        if any(k in n for k in ['飞书','lark']): return '飞书'
        if 'cn.gov' in p or '政务' in n: return '政务服务'
        return '办公协同'

    def close(self):
        self.client.close()
        self.db.close()

def main():
    c = DirectCrawlerV2()
    try:
        total = c.run()
        if total > 0:
            logger.info("\n导出...")
            from storage.db import CustomerDB
            from storage.exporter import DataExporter
            from pipeline.quality_scorer import QualityScorer
            QualityScorer(c.db).run()
            cdb = CustomerDB()
            exp = DataExporter(cdb, c.db)
            for name,path in exp.export_all().items():
                logger.info(f"已导出: {name} -> {path}")
            exp.print_summary()
            cdb.close()
    finally: c.close()

if __name__ == '__main__':
    main()
