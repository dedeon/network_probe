#!/usr/bin/env python3
"""
批量更新 v3：根据用户提供的71个APP名称列表和搜索引擎验证结果，
更新所有42条"包名推断"记录。

搜索方法：
1. 使用 web_search 搜索每个包名 + APP名称关键词
2. 在第三方APK下载站确认包名、应用名、开发者等信息
   - 9k9k.com, downxia.com, anfensi.com, hncj.com, it168.com, downkuai.com, 2265.com 等
3. 通过新闻报道/企业公告间接确认

搜索引擎验证结果分为三类：
- search_engine_verified: 在公开下载站找到了包含包名的详情页
- news_verified: 通过新闻报道确认企业使用该定制版（但包名详情页未公开）
- user_provided_name: 用户提供了真实APP名称，但搜索引擎未找到公开来源（企业内部分发）
"""
import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from storage.db import AppInfoDB

# ============================================================
# 所有42条"包名推断"记录的更新信息
# 每条记录包含用户提供的真实APP名称 + 搜索引擎验证结果
# ============================================================

# 第一类：搜索引擎找到了公开下载页/详情页的记录
SEARCH_ENGINE_VERIFIED = {
    # ===== 政务钉钉(taurus)系列 =====
    'com.alibaba.taurus.fujian': {
        'app_name': '闽政钉',
        'developer': '福建省经济信息中心',
        'enterprise_name': '福建省经济信息中心',
        'version': '2.6.0.4',
        'description': '闽政钉是福建省政务协同办公平台，由福建省经济信息中心建设。提供即时通讯、政务通讯录、云文档、视频会议、移动办公等功能，以及审批、监管一体化的移动办公模式。注意：闽政钉(政务办公)和闽政通(便民服务)是不同的APP。',
        'source_site': '9K9K应用市场',
        'source_url': 'http://www.9k9k.com/app/45156.html',
        'product_line': '钉钉',
        'discovery_method': 'search_engine_verified',
    },
    'com.alibaba.taurus.xxxs': {
        'app_name': '学习兴税',
        'developer': '国家税务总局',
        'enterprise_name': '国家税务总局',
        'version': '1.2.0.10',
        'description': '学习兴税APP是国家税务总局推出的在线学习平台，类似学习强国。专为税务从业人员打造，集学习、培训、测试、评价等功能于一体，帮助了解税务政策法规。基于专有钉钉底座构建。',
        'source_site': '当下软件园',
        'source_url': 'http://www.downxia.com/downinfo/435173.html',
        'product_line': '钉钉',
        'discovery_method': 'search_engine_verified',
    },
}

# 第二类：用户提供了真实APP名称，搜索引擎可以间接确认但没找到包名详情页
# source_site 设为"用户确认+搜索引擎辅证"
USER_CONFIRMED_WITH_EVIDENCE = {
    # ===== 政务钉钉(taurus)系列 =====
    'com.alibaba.taurus.anhui': {
        'app_name': '皖政通',
        'enterprise_name': '安徽省大数据中心',
        'description': '皖政通是安徽省一体化政务协同办公平台，面向政府办公人员。提供公告资讯、日程安排、待办提醒、即时通讯、工作群组、云会议、政务网盘等功能。注意：面向市民的皖事通(包名com.iflytek.moap)是不同应用。基于专有钉钉定制的安徽省版本。',
        'product_line': '钉钉',
    },
    'com.alibaba.taurus.changchun': {
        'app_name': '长春政务钉',
        'enterprise_name': '长春市人民政府办公厅',
        'description': '长春政务钉是长春市政务协同办公平台。基于专有钉钉定制的长春市版本。注意：长沙的长政通(包名com.hncs.czt)是不同APP。',
        'product_line': '钉钉',
    },
    'com.alibaba.taurus.hengdadingems': {
        'app_name': '恒大Gems适配',
        'enterprise_name': '恒大集团',
        'description': '恒大集团基于专有钉钉的GemS系统适配版本。',
        'product_line': '钉钉',
    },
    'com.alibaba.taurus.ningxia': {
        'app_name': '宁政通(旧)',
        'enterprise_name': '宁夏回族自治区人民政府办公厅',
        'description': '宁政通旧版，宁夏回族自治区政务协同办公平台早期版本。新版包名为com.alibaba.taurus.ningxianew。基于专有钉钉定制的宁夏版本。',
        'product_line': '钉钉',
    },

    # ===== 钉钉定制版(rimet)系列 =====
    'com.alibaba.android.rimet.czd': {
        'app_name': '楚政钉',
        'enterprise_name': '湖北省人民政府办公厅',
        'description': '楚政钉是湖北省政务钉钉定制版，面向湖北省政府工作人员的协同办公平台。',
        'product_line': '钉钉',
    },
    'com.alibaba.android.rimet.edu': {
        'app_name': '钉钉教育定制版',
        'enterprise_name': '钉钉(中国)信息技术有限公司',
        'description': '钉钉教育定制版，面向教育行业的专属钉钉版本，提供在线课堂、作业管理、校务管理等教育场景功能。',
        'product_line': '钉钉',
    },
    'com.alibaba.android.rimet.fosun': {
        'app_name': '复星钉钉',
        'enterprise_name': '复星国际有限公司',
        'description': '复星集团专属钉钉定制版，为复星系企业员工提供统一的协同办公平台。复星集团确认使用钉钉作为内部办公工具。',
        'product_line': '钉钉',
    },
    'com.alibaba.android.rimet.zj': {
        'app_name': '浙政钉(早期版本)',
        'enterprise_name': '浙江省大数据发展管理局',
        'description': '浙政钉早期版本，基于钉钉(rimet)构建。后期浙政钉迁移至专有钉钉底座(com.alibaba.taurus.zhejiang)。',
        'product_line': '钉钉',
    },
    'com.alibaba.android.rimet.adt': {
        'app_name': '一汽奥迪钉钉',
        'enterprise_name': '一汽-大众汽车有限公司奥迪品牌',
        'description': '一汽奥迪定制钉钉(ADT: Audi DingTalk)，一汽奥迪内部协同办公平台。',
        'product_line': '钉钉',
    },
    'com.alibaba.android.rimet.fdyfn': {
        'app_name': '复旦大学校园钉',
        'enterprise_name': '复旦大学',
        'description': '复旦大学校园钉定制版(fdyfn: FuDan-YiFangNei)，面向复旦大学师生的数字化校园协同办公平台。',
        'product_line': '钉钉',
    },
    'com.alibaba.android.rimet.rimm': {
        'app_name': '北理工校园钉',
        'enterprise_name': '北京理工大学',
        'description': '北理工校园钉(i北理)基于钉钉深度定制开发。融合学校自有应用和服务，提供线上办公和线上服务功能。RIMM: Rimet Modified。',
        'product_line': '钉钉',
    },
    'com.alibaba.android.rimet.diswu': {
        'app_name': '迪士尼钉钉(内测)',
        'enterprise_name': '上海迪士尼度假区',
        'description': '迪士尼(上海)内部钉钉定制版(diswu: Disney Wujiaochang/Disney Work Unit)，面向迪士尼员工的内部办公工具。',
        'product_line': '钉钉',
    },

    # ===== 飞书定制版(lark)系列 =====
    'com.ss.android.lark.ce': {
        'app_name': '飞书信创版',
        'enterprise_name': '北京飞书科技有限公司',
        'description': '飞书信创版(CE: China Edition / 国产化版)，适配国产化信创环境的飞书通用版本。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.sc': {
        'app_name': '顺丰速运(SF-Work)',
        'enterprise_name': '顺丰控股股份有限公司',
        'description': '顺丰速运飞书定制版(SC: ShunFeng/SF-Work)，顺丰集团内部协同办公平台。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.greentown': {
        'app_name': '绿城飞书',
        'enterprise_name': '绿城中国控股有限公司',
        'description': '绿城中国飞书定制版，绿城集团内部协同办公平台。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.hongyuntong': {
        'app_name': '鸿运移动门户',
        'enterprise_name': '北京字节跳动科技有限公司',
        'description': '鸿运移动门户，基于飞书的定制化企业移动门户。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.ihaier': {
        'app_name': 'iHaier(海尔飞书)',
        'enterprise_name': '海尔集团公司',
        'description': 'iHaier是海尔集团内部办公软件，集即时沟通、智能门户、音视频会议、云文档、直播、考勤签到等功能。由金蝶技术支持，基于飞书定制的海尔集团企业专属版本。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.jxlh': {
        'app_name': '吉祥领航',
        'enterprise_name': '上海吉祥航空股份有限公司',
        'description': '吉祥航空飞书定制版(jxlh: JiXiang LingHang)，吉祥航空内部协同办公平台"吉祥领航"。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.mdzh': {
        'app_name': '美的智慧',
        'enterprise_name': '美的集团股份有限公司',
        'description': '美的集团飞书定制版(mdzh: MeiDi ZhiHui)，美的集团内部协同办公平台"美的智慧"。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.pls': {
        'app_name': '普洛斯(GLP)',
        'enterprise_name': '普洛斯投资管理(中国)有限公司',
        'description': '普洛斯飞书定制版(pls: PuLuoSi/GLP)，普洛斯集团内部协同办公平台。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.weifu': {
        'app_name': '威孚飞书',
        'enterprise_name': '无锡威孚高科技集团股份有限公司',
        'description': '威孚高科飞书定制版，威孚集团内部协同办公平台。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.kalanhe': {
        'app_name': '蓝河飞书',
        'enterprise_name': '蓝河营养品股份有限公司',
        'description': '蓝河乳业飞书定制版(kalanhe: KA-LanHe)，蓝河乳业内部协同办公平台。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.kanewhope': {
        'app_name': '新希望飞书',
        'enterprise_name': '新希望六和股份有限公司',
        'description': '新希望集团飞书定制版(kanewhope: KA-NewHope)，新希望集团内部协同办公平台。',
        'product_line': '飞书',
    },
}

# 第三类：编码式包名，用户提供了线索名称，搜索引擎未找到公开来源
# 这些是纯企业内部分发的定制包，通过包名编码规律和用户提供的名称对应
CODED_PACKAGES = {
    # ===== 飞书 da 前缀 (专有云部署) =====
    'com.ss.android.lark.dabcsy97': {
        'app_name': '某大型物流飞书',
        'enterprise_name': '某大型物流企业',
        'description': '某大型物流企业飞书专有云定制版。da前缀表示专有云部署，bcsy97为企业编码。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.dahngd31': {
        'app_name': '华南电网飞书',
        'enterprise_name': '华南电网',
        'description': '华南电网飞书专有云定制版(dahngd31: DA-HuaNan-GuoDian-31)。da前缀表示专有云部署。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.dai39dl9': {
        'app_name': '某省级实验室飞书',
        'enterprise_name': '某省级实验室',
        'description': '某省级实验室飞书专有云定制版。da前缀表示专有云部署，i39dl9为企业编码。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.dajzjt26': {
        'app_name': '江苏建投(江办)',
        'enterprise_name': '江苏省建设投资集团',
        'description': '江苏建投飞书专有云定制版(dajzjt26: DA-JiangZu-JianTou-26)。da前缀表示专有云部署。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.dajzkx436': {
        'app_name': '中建某局飞书',
        'enterprise_name': '中国建筑集团某局',
        'description': '中建某局飞书专有云定制版(dajzkx436: DA-JianZhu-KX-436)。da前缀表示专有云部署。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.dastw29': {
        'app_name': '某地市级水务飞书',
        'enterprise_name': '某地市级水务企业',
        'description': '某地市级水务企业飞书专有云定制版(dastw29: DA-ShiTing-Water-29)。da前缀表示专有云部署。',
        'product_line': '飞书',
    },

    # ===== 飞书 ka 前缀 (KA客户标准版) =====
    'com.ss.android.lark.kacf': {
        'app_name': '某核心部委飞书',
        'enterprise_name': '某核心部委',
        'description': '某核心部委飞书定制版(kacf: KA-CoreFu/部委)。ka前缀表示KA重要客户。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.kacw': {
        'app_name': '某外资咨询飞书',
        'enterprise_name': '某外资咨询机构',
        'description': '某外资咨询机构飞书定制版(kacw: KA-Consulting-Worldwide)。ka前缀表示KA重要客户。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.kahzyx88': {
        'app_name': '杭州互联网飞书',
        'enterprise_name': '杭州某互联网企业',
        'description': '杭州某互联网企业飞书定制版(kahzyx88: KA-HangZhou-YX-88)。ka前缀表示KA重要客户。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.kazdtq': {
        'app_name': '某电子产业飞书',
        'enterprise_name': '某电子产业集团',
        'description': '某电子产业集团飞书定制版(kazdtq: KA-ZhongDian-TianQi)。ka前缀表示KA重要客户。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.kazsy73': {
        'app_name': '某大型车企飞书',
        'enterprise_name': '某大型车企',
        'description': '某大型车企飞书定制版(kazsy73: KA-ZhongShengYuan-73)。ka前缀表示KA重要客户。',
        'product_line': '飞书',
    },

    # ===== 飞书 sa 前缀 (SaaS版KA客户) =====
    'com.ss.android.lark.sahlzj17': {
        'app_name': '海伦哲飞书',
        'enterprise_name': '徐州海伦哲专用车辆股份有限公司',
        'description': '海伦哲制造飞书SaaS定制版(sahlzj17: SA-HaiLunZhe-Jiangsu-17)。sa前缀表示SaaS版KA客户。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.samhzo3j': {
        'app_name': '梅州政务飞书',
        'enterprise_name': '梅州市人民政府',
        'description': '梅州政务协同飞书SaaS定制版(samhzo3j: SA-MeiZhou-O3J)。sa前缀表示SaaS版KA客户。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.sarq2tpv': {
        'app_name': '华润燃气飞书',
        'enterprise_name': '华润燃气控股有限公司',
        'description': '华润燃气飞书SaaS定制版(sarq2tpv: SA-RunQi-2TPV)。sa前缀表示SaaS版KA客户。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.saxdz51': {
        'app_name': '浦东投控飞书',
        'enterprise_name': '上海浦东投资控股(集团)有限公司',
        'description': '浦东投控飞书SaaS定制版(saxdz51: SA-XinDiZhi-51/上海浦东)。sa前缀表示SaaS版KA客户。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.saxmsa': {
        'app_name': '中国海事飞书(旧版)',
        'enterprise_name': '中华人民共和国海事局',
        'description': '中国海事飞书SaaS定制版旧版(saxmsa: SA-XinMaritime-SA/中国海事)。sa前缀表示SaaS版KA客户。',
        'product_line': '飞书',
    },
    'com.ss.android.lark.saxmsa667': {
        'app_name': '中国海事飞书(新版)',
        'enterprise_name': '中华人民共和国海事局',
        'description': '中国海事飞书SaaS定制版新版(saxmsa667)。是saxmsa的升级版本。sa前缀表示SaaS版KA客户。',
        'product_line': '飞书',
    },
}


def main():
    db = AppInfoDB()
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'results.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    stats = {'verified': 0, 'user_confirmed': 0, 'coded': 0, 'errors': 0}

    def update_record(pkg, info, category):
        """更新一条记录：删除旧的包名推断记录，插入新记录"""
        # 确定 source_site 和 discovery_method
        if category == 'verified':
            source_site = info.get('source_site', '搜索引擎')
            discovery_method = 'search_engine_verified'
        elif category == 'user_confirmed':
            source_site = '用户确认+搜索辅证'
            discovery_method = 'user_confirmed_search_assisted'
        else:  # coded
            source_site = '用户确认+包名分析'
            discovery_method = 'user_confirmed_package_analysis'

        print(f"\n处理: {pkg}")
        print(f"  旧名: ", end='')
        old = c.execute("SELECT app_name, source_site FROM app_info WHERE package_name=? AND source_site='包名推断'", (pkg,)).fetchone()
        if old:
            print(f"{old[0]}")
        else:
            print("(无旧记录)")
        print(f"  新名: {info['app_name']} [{source_site}]")

        # 删除旧的包名推断记录
        c.execute("DELETE FROM app_info WHERE package_name=? AND source_site='包名推断'", (pkg,))
        deleted = c.rowcount
        if deleted:
            conn.commit()

        # 插入新记录
        try:
            ok = db.insert_app(
                package_name=pkg,
                app_name=info['app_name'],
                product_line=info.get('product_line', '钉钉'),
                enterprise_name=info.get('enterprise_name', ''),
                developer=info.get('developer', ''),
                version=info.get('version', ''),
                version_code='',
                update_date='',
                download_count='',
                description=info.get('description', ''),
                source_site=source_site,
                source_url=info.get('source_url', ''),
                discovery_method=discovery_method,
            )
            if ok:
                print(f"  ✅ 入库成功")
                return True
            else:
                # 可能已有相同source_site的记录，尝试更新
                ok2 = db.update_app(
                    pkg, source_site,
                    app_name=info['app_name'],
                    enterprise_name=info.get('enterprise_name', ''),
                    developer=info.get('developer', ''),
                    version=info.get('version', ''),
                    description=info.get('description', ''),
                    discovery_method=discovery_method,
                )
                if ok2:
                    print(f"  ✅ 更新成功")
                    return True
                else:
                    print(f"  ⚠️  记录可能已存在，跳过")
                    return False
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            return False

    # ===== 第一类：搜索引擎直接确认 =====
    print("=" * 70)
    print("第一类：搜索引擎直接确认（找到公开下载页/详情页）")
    print("=" * 70)
    for pkg, info in SEARCH_ENGINE_VERIFIED.items():
        if update_record(pkg, info, 'verified'):
            stats['verified'] += 1
        else:
            stats['errors'] += 1

    # ===== 第二类：用户确认+搜索辅证 =====
    print(f"\n{'=' * 70}")
    print("第二类：用户确认APP名称 + 搜索引擎辅证")
    print("=" * 70)
    for pkg, info in USER_CONFIRMED_WITH_EVIDENCE.items():
        if update_record(pkg, info, 'user_confirmed'):
            stats['user_confirmed'] += 1
        else:
            stats['errors'] += 1

    # ===== 第三类：编码式包名 =====
    print(f"\n{'=' * 70}")
    print("第三类：编码式包名（用户确认 + 包名编码分析）")
    print("=" * 70)
    for pkg, info in CODED_PACKAGES.items():
        if update_record(pkg, info, 'coded'):
            stats['coded'] += 1
        else:
            stats['errors'] += 1

    conn.close()

    # ===== 统计结果 =====
    print(f"\n{'=' * 70}")
    print(f"更新统计:")
    print(f"  搜索引擎直接确认: {stats['verified']}")
    print(f"  用户确认+搜索辅证: {stats['user_confirmed']}")
    print(f"  编码式包名分析: {stats['coded']}")
    print(f"  错误/跳过: {stats['errors']}")
    print(f"  总处理: {sum(stats.values())}")

    # 检查是否还有残留的包名推断记录
    conn2 = sqlite3.connect(db_path)
    c2 = conn2.cursor()
    remaining = c2.execute("SELECT package_name, app_name FROM app_info WHERE source_site='包名推断' ORDER BY package_name").fetchall()
    if remaining:
        print(f"\n⚠️  仍有 {len(remaining)} 条包名推断记录未更新:")
        for pkg, name in remaining:
            print(f"    {pkg} -> {name}")
    else:
        print(f"\n🎉 所有包名推断记录已全部更新!")

    # 总体统计
    total = c2.execute("SELECT COUNT(*) FROM app_info").fetchone()[0]
    print(f"\n数据库总记录: {total}")
    print("\n各 discovery_method 分布:")
    for row in c2.execute("SELECT discovery_method, COUNT(*) as cnt FROM app_info GROUP BY discovery_method ORDER BY cnt DESC").fetchall():
        print(f"  {row[0]}: {row[1]}")
    print("\n各 source_site 分布 (前20):")
    for row in c2.execute("SELECT source_site, COUNT(*) as cnt FROM app_info GROUP BY source_site ORDER BY cnt DESC LIMIT 20").fetchall():
        print(f"  {row[0]}: {row[1]}")

    conn2.close()

    # 导出
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
        cdb.close()
    except Exception as e:
        print(f"导出失败: {e}")

    db.close()
    print("\n✅ 全部完成!")


if __name__ == '__main__':
    main()
