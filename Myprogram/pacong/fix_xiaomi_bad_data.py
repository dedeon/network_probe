#!/usr/bin/env python3
"""
修复小米应用商店返回的无效数据
小米对不存在的包名不返回404，而是返回通用首页，导致app_name全是"手机游戏应用商店_软件商店app下载"
需要：
1. 删除这54条错误数据
2. 用基于包名规律推断的正确信息重新入库
"""
import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from storage.db import AppInfoDB

# 包名后缀到(应用名, 企业名)的映射
FEISHU_SUFFIX_MAP = {
    'kaahyz17': ('飞书定制版(kaahyz17)', ''),
    'kahzyx88': ('飞书定制版(kahzyx88)', ''),
    'kazdtq': ('飞书定制版(kazdtq)', ''),
    'kazsy73': ('飞书定制版(kazsy73)', ''),
    'dabcsy97': ('飞书定制版(dabcsy97)', ''),
    'dagtjt11': ('飞书定制版(dagtjt11)', ''),
    'dahngd31': ('飞书定制版(dahngd31)', ''),
    'dai39dl9': ('飞书定制版(dai39dl9)', ''),
    'dajzjt26': ('飞书定制版(dajzjt26)', ''),
    'dajzkx436': ('飞书定制版(dajzkx436)', ''),
    'dastw29': ('飞书定制版(dastw29)', ''),
    'greentown': ('绿城飞书', '绿城中国控股有限公司'),
    'hongyuntong': ('鸿运通', ''),
    'htone': ('H-One飞书', ''),
    'ihaier': ('海尔飞书', '海尔集团公司'),
    'jxlh': ('江西联合飞书', ''),
    'mdzh': ('美的飞书', '美的集团股份有限公司'),
    'pls': ('普洛斯飞书', '普洛斯投资管理(中国)有限公司'),
    'sacbdn67new': ('飞书定制版(sacbdn67new)', ''),
    'sahlzj17': ('飞书定制版(sahlzj17)', ''),
    'samhzo3j': ('飞书定制版(samhzo3j)', ''),
    'sapdl18': ('飞书定制版(sapdl18)', ''),
    'sarq2tpv': ('飞书定制版(sarq2tpv)', ''),
    'saxdz51': ('飞书定制版(saxdz51)', ''),
    'saxmsa': ('飞书定制版(saxmsa)', ''),
    'saxmsa667': ('飞书定制版(saxmsa667)', ''),
    'weifu': ('威孚飞书', '无锡威孚高科技集团股份有限公司'),
    'ce': ('飞书CE版', ''),
    'kacf': ('飞书定制版(kacf)', ''),
    'kacw': ('飞书定制版(kacw)', ''),
    'sc': ('飞书SC版', ''),
    'kalanhe': ('蓝河飞书', '蓝河营养品股份有限公司'),
    'kanewhope': ('新希望飞书', '新希望六和股份有限公司'),
}

DINGDING_SUFFIX_MAP = {
    'adt': ('钉钉ADT版', ''),
    'aliding': ('阿里钉', '阿里巴巴集团控股有限公司'),
    'bgyfw': ('碧桂园服务钉钉', '碧桂园生活服务集团股份有限公司'),
    'catlcome': ('宁德时代钉钉', '宁德时代新能源科技股份有限公司'),
    'ccflink': ('中汽联钉钉', ''),
    'czd': ('楚政钉', ''),
    'diswu': ('钉钉定制版(diswu)', ''),
    'fdyfn': ('钉钉定制版(fdyfn)', ''),
    'fosun': ('复星钉钉', '复星国际有限公司'),
    'rimm': ('钉钉RIMM版', ''),
    'zj': ('浙江钉钉', ''),
    'edu': ('钉钉教育版', ''),
}

TAURUS_SUFFIX_MAP = {
    'changchun': ('长政通', '长春市人民政府办公厅'),
    'cpic': ('太保政钉', '中国太平洋保险(集团)股份有限公司'),
    'fujian': ('闽政通', '福建省人民政府办公厅'),
    'hengdadingems': ('恒大政钉', ''),
    'jiangxi': ('赣政通', '江西省人民政府办公厅'),
    'ningxia': ('宁政通', '宁夏回族自治区人民政府办公厅'),
    'qzt': ('秦政通', '陕西省人民政府办公厅'),
    'xxxs': ('新疆政务钉钉', ''),
    'anhui': ('皖政通', '安徽省人民政府办公厅'),
}


def main():
    conn = sqlite3.connect('output/results.db')
    c = conn.cursor()
    
    # 1. 找出所有小米来源的错误数据
    c.execute("SELECT package_name, app_name FROM app_info WHERE source_site='小米应用商店'")
    bad_rows = c.fetchall()
    print(f"找到 {len(bad_rows)} 条小米来源数据需要修复")
    
    # 2. 逐条修复
    fixed = 0
    for pkg, old_name in bad_rows:
        new_name = None
        enterprise = ''
        developer = ''
        description = ''
        discovery_method = 'inferred_custom_package'
        
        if pkg.startswith('com.ss.android.lark.'):
            suffix = pkg.replace('com.ss.android.lark.', '')
            if suffix in FEISHU_SUFFIX_MAP:
                new_name, enterprise = FEISHU_SUFFIX_MAP[suffix]
            else:
                new_name = f'飞书定制版({suffix})'
            developer = '北京飞书科技有限公司'
            if not enterprise:
                enterprise = '北京字节跳动科技有限公司'
            description = f'飞书(Lark)企业定制安卓版本。包名: {pkg}，基于飞书基座(com.ss.android.lark)定制开发的企业专属移动办公应用。'
            discovery_method = 'inferred_feishu_custom'
            
        elif pkg.startswith('com.alibaba.android.rimet.'):
            suffix = pkg.replace('com.alibaba.android.rimet.', '')
            if suffix in DINGDING_SUFFIX_MAP:
                new_name, enterprise = DINGDING_SUFFIX_MAP[suffix]
            else:
                new_name = f'钉钉定制版({suffix})'
            developer = '钉钉(中国)信息技术有限公司'
            if not enterprise:
                enterprise = '阿里巴巴集团控股有限公司'
            description = f'钉钉(DingTalk)企业定制安卓版本。包名: {pkg}，基于钉钉基座(com.alibaba.android.rimet)定制开发的企业专属移动办公应用。'
            discovery_method = 'inferred_dingding_custom'
            
        elif pkg.startswith('com.alibaba.taurus.'):
            suffix = pkg.replace('com.alibaba.taurus.', '')
            if suffix in TAURUS_SUFFIX_MAP:
                new_name, enterprise = TAURUS_SUFFIX_MAP[suffix]
            else:
                new_name = f'政务钉钉-{suffix}版'
            developer = '钉钉(中国)信息技术有限公司'
            if not enterprise:
                enterprise = ''
            description = f'政务钉钉(浙政钉系列)地方定制安卓版本。包名: {pkg}，基于浙政钉基座(com.alibaba.taurus)定制开发的政务专属移动办公应用。'
            discovery_method = 'inferred_taurus_custom'
        
        if new_name:
            c.execute("""UPDATE app_info SET 
                app_name=?, enterprise_name=?, developer=?, 
                description=?, source_site=?, discovery_method=?
                WHERE package_name=?""",
                (new_name, enterprise, developer, description, '包名推断', discovery_method, pkg))
            fixed += 1
            print(f"  ✅ {pkg} -> {new_name} ({enterprise or '-'})")
    
    conn.commit()
    print(f"\n修复了 {fixed}/{len(bad_rows)} 条记录")
    
    # 3. 验证修复结果
    c.execute("SELECT package_name, app_name, enterprise_name, source_site FROM app_info WHERE source_site='包名推断' ORDER BY package_name")
    rows = c.fetchall()
    print(f"\n=== 修复后的推断数据 ({len(rows)} 条) ===")
    for r in rows:
        print(f"  {r[0]:50s} | {r[1]:25s} | {r[2]:25s} | {r[3]}")
    
    conn.close()
    
    # 4. 重新执行质量评分和导出
    print("\n重新执行质量评分和导出...")
    db = AppInfoDB()
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
    print("\n完成!")


if __name__ == '__main__':
    main()
