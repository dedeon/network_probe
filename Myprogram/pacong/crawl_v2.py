#!/usr/bin/env python3
"""v2爬虫 - 修复应用宝解析 + 滚雪球"""
import httpx, re, json, time, random, os, sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from storage.db import AppInfoDB
from utils.logger import setup_logger, get_logger

setup_logger()
logger = get_logger('direct_crawler')

# (包名, 产品线, 备注)
KNOWN = [
    # 腾讯16个
    ('com.tencent.wework','企业微信',''),('com.tencent.docs','企业微信',''),
    ('com.tencent.tim','企业微信',''),('com.tencent.mobileqq','企业微信',''),
    ('com.tencent.mm','企业微信',''),('com.tencent.qqmail','企业微信',''),
    ('com.tencent.map','企业微信',''),('com.tencent.qqlive','企业微信',''),
    ('com.tencent.qqmusic','企业微信',''),('com.tencent.karaoke','企业微信',''),
    ('com.tencent.weishi','企业微信',''),('com.tencent.news','企业微信',''),
    ('com.tencent.mtt','企业微信',''),('com.tencent.wetype','企业微信',''),
    ('com.tencent.reading','企业微信',''),('com.tencent.androidqqmanager','企业微信',''),
    # 阿里13个
    ('com.alibaba.android.rimet','钉钉',''),('com.alibaba.aliyun','钉钉',''),
    ('com.taobao.taobao','钉钉',''),('com.eg.android.AlipayGphone','钉钉',''),
    ('com.taobao.idlefish','钉钉',''),('com.alibaba.wireless.ichangmessenger','钉钉',''),
    ('com.tmall.wireless','钉钉',''),('com.UCMobile','钉钉',''),
    ('com.autonavi.minimap','钉钉',''),('com.youku.phone','钉钉',''),
    ('com.taobao.trip','钉钉',''),('com.cainiao.wireless.homepage','钉钉',''),
    ('com.alibaba.teambition','钉钉',''),
    # 字节9个
    ('com.ss.android.lark','飞书',''),('com.ss.android.article.news','飞书',''),
    ('com.ss.android.ugc.aweme','飞书',''),('com.ss.android.ugc.aweme.lite','飞书',''),
    ('com.ss.android.article.lite','飞书',''),('com.ss.android.ugc.live','飞书',''),
    ('com.ss.android.auto','飞书',''),('com.ss.android.article.video','飞书',''),
    ('com.luna.music','飞书',''),
    # 办公13个
    ('cn.wps.moffice_eng','办公协同',''),('cn.wps.yun','办公协同',''),
    ('com.huawei.welink','办公协同',''),('com.seeyon.cmp','办公协同',''),
    ('com.weaver.emobile7','办公协同',''),('com.inspur.emmcloud','办公协同',''),
    ('com.microsoft.teams','办公协同',''),('com.microsoft.office.outlook','办公协同',''),
    ('com.microsoft.skydrive','办公协同',''),('com.microsoft.office.word','办公协同',''),
    ('com.microsoft.office.excel','办公协同',''),('com.microsoft.office.powerpoint','办公协同',''),
    ('com.microsoft.office.onenote','办公协同',''),
    # 银行11个
    ('com.icbc','办公协同',''),('com.chinamworld.bocmbci','办公协同',''),
    ('com.ecitic.bank.mobile','办公协同',''),('cmb.pb','办公协同',''),
    ('com.chinamworld.main','办公协同',''),('com.android.bankabc','办公协同',''),
    ('com.bankcomm.Bankcomm','办公协同',''),('com.pingan.papd','办公协同',''),
    ('com.yitong.mbank.psbc','办公协同',''),('com.spdb.mobilebankN','办公协同',''),
    ('com.cib.cibmb','办公协同',''),
    # 招聘/通讯/笔记7个
    ('com.netease.mail','办公协同',''),('com.zhaopin.social','办公协同',''),
    ('com.nowcoder.app.florida','办公协同',''),('com.hpbr.bosszhipin','办公协同',''),
    ('com.yinxiang','办公协同',''),('com.youdao.note','办公协同',''),
    ('com.baidu.netdisk','办公协同',''),
    # 政务
    ('com.hanweb.android.zhejiang.activity','政务服务',''),
    # 社交/媒体/搜索/输入法8个
    ('com.sina.weibo','办公协同',''),('com.zhihu.android','办公协同',''),
    ('tv.danmaku.bili','办公协同',''),('com.xingin.xhs','办公协同',''),
    ('com.baidu.searchbox','办公协同',''),('com.baidu.BaiduMap','办公协同',''),
    ('com.baidu.input','办公协同',''),('com.iflytek.inputmethod','办公协同',''),
    # 出行/生活5个
    ('com.sdu.didi.psnger','办公协同',''),('ctrip.android.view','办公协同',''),
    ('com.MobileTicket','办公协同',''),('com.netease.cloudmusic','办公协同',''),
    ('com.kuaishou.nebula','办公协同',''),
    # 电商5个
    ('com.jingdong.app.mall','办公协同',''),('com.xunmeng.pinduoduo','办公协同',''),
    ('com.meituan','办公协同',''),('com.dianping.v1','办公协同',''),
    ('com.sankuai.meituan.takeoutnew','办公协同',''),
    # 视频4个
    ('com.qiyi.video','办公协同',''),('com.kugou.android','办公协同',''),
    ('com.ximalaya.ting.android','办公协同',''),('com.hunantv.imgo.activity','办公协同',''),
    # 工具/金融/其他12个
    ('com.todesk','办公协同',''),('com.oray.sunlogin','办公协同',''),
    ('com.youdao.dict','办公协同',''),('com.camscanner.online','办公协同',''),
    ('com.eastmoney.android.berlin','办公协同',''),('com.hexin.plat.android','办公协同',''),
    ('com.chinaums.pmp','办公协同',''),('com.sf.activity','办公协同',''),
    ('com.xunlei.downloadprovider','办公协同',''),('com.cubic.autohome','办公协同',''),
    ('com.fenbi.android.servant','办公协同',''),('com.chaoxing.mobile','办公协同',''),
    ('us.zoom.videomeetings','办公协同',''),('com.gotokeep.keep','办公协同',''),
    ('com.tongcheng.android','办公协同',''),('com.baidu.translate','办公协同',''),
    ('com.netease.newsreader.activity','办公协同',''),('com.suning.mobile.ebuy','办公协同',''),
]


class CrawlerV2:
    def __init__(self):
        self.db = AppInfoDB()
        self.client = httpx.Client(timeout=20, follow_redirects=True, verify=False,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                     ' (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                     'Accept-Language': 'zh-CN,zh;q=0.9'})
        self.found = set()
        self.checked = set()
        self.recommend_queue = []
        self.n_known = 0
        self.n_snow = 0

    def run(self):
        logger.info(f"v2爬虫启动, 已知{len(KNOWN)}个包名")
        self._clean()
        logger.info("--- 阶段1: 验证已知包名 ---")
        self._phase1()
        logger.info("--- 阶段2: 滚雪球 ---")
        self._phase2()
        total = self.db.count()
        logger.info(f"完成! 总{total}, 已知{self.n_known}, 滚雪球{self.n_snow}")
        return total

    def _clean(self):
        try:
            c = self.db._get_conn()
            c.execute('DELETE FROM app_info')
            c.commit()
        except Exception:
            pass

    def _phase1(self):
        for i, (pkg, pl, _) in enumerate(KNOWN):
            if pkg in self.checked:
                continue
            if i % 20 == 0 and i > 0:
                logger.info(f"  进度 {i}/{len(KNOWN)}, 发现{self.n_known}")
            info = self._fetch(pkg)
            if info:
                info['product_line'] = pl
                if self._save(info):
                    self.n_known += 1
            self.checked.add(pkg)
            time.sleep(random.uniform(0.15, 0.4))
        logger.info(f"阶段1: {self.n_known}/{len(KNOWN)}")

    def _phase2(self):
        for rnd in range(1, 4):
            batch = list(set(self.recommend_queue))
            self.recommend_queue = []
            new = [p for p in batch if p not in self.checked]
            if not new:
                break
            logger.info(f"  第{rnd}轮: {len(new)}个")
            rf = 0
            for i, pkg in enumerate(new):
                if pkg in self.checked:
                    continue
                if i % 30 == 0 and i > 0:
                    logger.info(f"    {i}/{len(new)}, +{rf}")
                info = self._fetch(pkg)
                if info:
                    info['product_line'] = self._guess_pl(pkg, info.get('app_name', ''))
                    if self._save(info):
                        self.n_snow += 1
                        rf += 1
                self.checked.add(pkg)
                time.sleep(random.uniform(0.15, 0.4))
            logger.info(f"  轮{rnd}: +{rf}, 总{len(self.found)}")

    def _fetch(self, pkg):
        """从应用宝详情页获取信息"""
        url = f'https://sj.qq.com/appdetail/{pkg}'
        try:
            r = self.client.get(url)
            if r.status_code != 200 or len(r.text) < 2000:
                return None
            info = {'package_name': pkg, 'url': url}
            # 从__NEXT_DATA__提取
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
            if m:
                try:
                    nd = json.loads(m.group(1))
                    pp = nd.get('props', {}).get('pageProps', {})
                    dcr = pp.get('dynamicCardResponse', {}).get('data', {})
                    if isinstance(dcr, dict):
                        for comp in dcr.get('components', []):
                            cd = comp.get('data', {})
                            if not isinstance(cd, dict):
                                continue
                            if cd.get('name') == 'GameDetail':
                                items = cd.get('itemData', [])
                                if isinstance(items, str):
                                    items = json.loads(items)
                                if isinstance(items, list) and items:
                                    it = items[0]
                                    for k, ik in [('app_name','name'),('developer','developer'),
                                                  ('version','version_name'),('enterprise_name','operator')]:
                                        if it.get(ik):
                                            info[k] = it[ik]
                                    if it.get('download_num'):
                                        info['download_count'] = str(it['download_num'])
                                    if it.get('description'):
                                        info['description'] = str(it['description'])[:500]
                            if cd.get('name') in ('YouMayAlsoLike', 'SameDeveloper'):
                                its = cd.get('itemData', [])
                                if isinstance(its, str):
                                    its = json.loads(its)
                                if isinstance(its, list):
                                    for x in its:
                                        if isinstance(x, dict) and x.get('pkg_name'):
                                            self.recommend_queue.append(x['pkg_name'])
                    seo = pp.get('seoMeta', {})
                    if not info.get('app_name') and seo.get('title'):
                        info['app_name'] = self._ptitle(seo['title'])
                    if not info.get('description') and seo.get('description'):
                        info['description'] = seo['description'][:500]
                except Exception:
                    pass
            # 备用: HTML title
            if not info.get('app_name'):
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(r.text, 'lxml')
                t = soup.select_one('title')
                if t:
                    tt = t.get_text(strip=True)
                    if '找不到' in tt or '404' in tt:
                        return None
                    info['app_name'] = self._ptitle(tt)
            return info if info.get('app_name') else None
        except Exception:
            return None

    def _ptitle(self, title):
        if not title:
            return None
        n = re.sub(r'-应用宝.*$', '', title).strip()
        if '-' in n:
            n = n.split('-')[0].strip()
        n = re.sub(r'(app|APP|App).*$', '', n).strip()
        n = re.sub(r'(官方|官网|免费|最新|下载|安装|正版|版本).*$', '', n).strip()
        return n if n and len(n) >= 1 and '应用宝' not in n else None

    def _save(self, info):
        pkg = info.get('package_name', '')
        name = info.get('app_name', '')
        pl = info.get('product_line', '办公协同')
        if not pkg or not name or pkg in self.found:
            return False
        try:
            ok = self.db.insert_app(
                package_name=pkg, app_name=name, product_line=pl,
                enterprise_name=info.get('enterprise_name', ''),
                developer=info.get('developer', ''),
                version=info.get('version', ''), version_code='',
                update_date='', download_count=info.get('download_count', ''),
                description=info.get('description', ''),
                source_site='应用宝', source_url=info.get('url', ''),
                discovery_method='yingyongbao_v2')
            if ok:
                self.found.add(pkg)
                logger.info(f"  + {pkg:40s} | {name[:20]:20s} | {pl}")
            return ok
        except Exception:
            return False

    def _guess_pl(self, pkg, name):
        p, n = pkg.lower(), (name or '').lower()
        if 'tencent' in p:
            return '企业微信'
        if any(k in p for k in ['alibaba','taobao','alipay','rimet','autonavi','youku','cainiao','tmall','ucmobile']):
            return '钉钉'
        if any(k in p for k in ['ss.android','bytedance','lark','luna.music']):
            return '飞书'
        if '企业微信' in n or 'wework' in n:
            return '企业微信'
        if '钉钉' in n or 'dingtalk' in n:
            return '钉钉'
        if '飞书' in n or 'lark' in n:
            return '飞书'
        if 'cn.gov' in p or '政务' in n:
            return '政务服务'
        return '办公协同'

    def close(self):
        self.client.close()
        self.db.close()


def main():
    c = CrawlerV2()
    try:
        total = c.run()
        if total > 0:
            logger.info("导出...")
            from storage.db import CustomerDB
            from storage.exporter import DataExporter
            from pipeline.quality_scorer import QualityScorer
            QualityScorer(c.db).run()
            cdb = CustomerDB()
            exp = DataExporter(cdb, c.db)
            for nm, pa in exp.export_all().items():
                logger.info(f"  {nm} -> {pa}")
            exp.print_summary()
            cdb.close()
    finally:
        c.close()


if __name__ == '__main__':
    main()
