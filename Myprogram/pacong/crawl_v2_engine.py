import httpx,re,json,time,random,os,sys
from typing import Optional
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from storage.db import AppInfoDB
from utils.logger import setup_logger,get_logger
setup_logger()
L=get_logger("direct_crawler")
from crawl_v2 import KNOWN

def _fetch(cl,pkg,rq):
 url=f"https://sj.qq.com/appdetail/{pkg}"
 try:
  r=cl.get(url)
  if r.status_code!=200 or len(r.text)<2000:return None
  info={"package_name":pkg,"url":url}
  m=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',r.text,re.DOTALL)
  if m:
   try:
    nd=json.loads(m.group(1))
    pp=nd.get("props",{}).get("pageProps",{})
    dcr=pp.get("dynamicCardResponse",{}).get("data",{})
    if isinstance(dcr,dict):
     for comp in dcr.get("components",[]):
      cd=comp.get("data",{})
      if not isinstance(cd,dict):continue
      if cd.get("name")=="GameDetail":
       items=cd.get("itemData",[])
       if isinstance(items,str):items=json.loads(items)
       if isinstance(items,list) and items:
        it=items[0]
        M=[("app_name","name"),("developer","developer"),("version","version_name"),("enterprise_name","operator")]
        for k,ik in M:
         if it.get(ik):info[k]=it[ik]
        if it.get("download_num"):info["download_count"]=str(it["download_num"])
        if it.get("description"):info["description"]=str(it["description"])[:500]
      if cd.get("name") in ("YouMayAlsoLike","SameDeveloper"):
       its=cd.get("itemData",[])
       if isinstance(its,str):its=json.loads(its)
       if isinstance(its,list):
        for x in its:
         if isinstance(x,dict) and x.get("pkg_name"):rq.append(x["pkg_name"])
    seo=pp.get("seoMeta",{})
    if not info.get("app_name") and seo.get("title"):info["app_name"]=_pt(seo["title"])
    if not info.get("description") and seo.get("description"):info["description"]=seo["description"][:500]
   except Exception:pass
  if not info.get("app_name"):
   from bs4 import BeautifulSoup
   soup=BeautifulSoup(r.text,"lxml")
   t=soup.select_one("title")
   if t:
    tt=t.get_text(strip=True)
    if len(tt)<5 or chr(25214)+chr(19981)+chr(21040) in tt or "404" in tt:return None
    info["app_name"]=_pt(tt)
  return info if info.get("app_name") else None
 except Exception:return None

def _pt(title):
 if not title:return None
 n=re.sub(r"-应用宝.*$","",title).strip()
 if "-" in n:n=n.split("-")[0].strip()
 n=re.sub(r"(app|APP|App).*$","",n).strip()
 n=re.sub(r"(官方|官网|免费|最新|下载|安装|正版|版本).*$","",n).strip()
 return n if n and len(n)>=1 and "应用宝" not in n else None

def _gpl(pkg,name):
 p=pkg.lower();n=(name or"").lower()
 if "tencent" in p:return chr(20225)+chr(19994)+chr(24494)+chr(20449)
 A="alibaba taobao alipay rimet autonavi youku cainiao tmall ucmobile".split()
 if any(k in p for k in A):return chr(38025)*2
 B="ss.android bytedance lark luna.music".split()
 if any(k in p for k in B):return chr(39134)+chr(20070)
 if "cn.gov" in p:return chr(25919)+chr(21153)+chr(26381)+chr(21153)
 return chr(21150)+chr(20844)+chr(21327)+chr(21516)

