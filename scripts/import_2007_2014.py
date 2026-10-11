#!/usr/bin/env python3
"""Download/validate official 2007–2014 Kagawa annual statistics; extend index.html."""
import csv,json,re,time,unicodedata
from pathlib import Path
from bs4 import BeautifulSoup
import requests

ROOT=Path(__file__).resolve().parents[1]
BASE="https://opendata.pref.kagawa.lg.jp"
SOURCES={2007:(834,14667,14669),2008:(835,14684,14686),
 2009:(836,14701,14703),2010:(839,14749,14751),
 2011:(838,14733,14735),2012:(840,14756,14758),
 2013:(217,1768,1770),2014:(218,1784,1786)}
NAMES="高松市 丸亀市 坂出市 善通寺市 観音寺市 さぬき市 東かがわ市 三豊市 土庄町 小豆島町 三木町 直島町 宇多津町 綾川町 琴平町 多度津町 まんのう町".split()
def clean(s):return re.sub(r"\s+","",unicodedata.normalize("NFKC",str(s or "")))
def num(s):
 s=unicodedata.normalize("NFKC",str(s or "")).replace(",","").replace(" ","")
 s=s.replace("▲","-").replace("△","-").replace("−","-").replace("－","-")
 return float(s) if re.fullmatch(r"[+-]?\d+(?:\.\d+)?",s) else None
def intval(x):
 if x is None or int(x)!=x:raise ValueError("Noninteger value: "+str(x))
 return int(x)
def source(year,rid):
 did=SOURCES[year][0];url=f"{BASE}/dataset/{did}/resource/{rid}/content.html"
 for trial in range(4):
  try:
   r=requests.get(url,timeout=35,headers={"User-Agent":"Mozilla/5.0"})
   r.raise_for_status()
   soup=BeautifulSoup(r.content,"html.parser")
   if not soup.select("table tr"):raise RuntimeError("No table at "+url)
   return url,soup
  except (requests.RequestException,RuntimeError):
   if trial==3:raise
   time.sleep((trial+1)*2)
def extract(soup):
 found={};pref=None
 for tr in soup.select("tr"):
  cells=[c.get_text(" ",strip=True) for c in tr.find_all(["td","th"],recursive=False)]
  if not cells:continue
  normalized=[clean(c) for c in cells]
  key=next((n for n in NAMES if n in normalized),None)
  pi=next((i for i,v in enumerate(normalized) if v in ("香川県","県計")),None)
  if key:
   i=normalized.index(key);values=[v for v in (num(s) for s in cells[i+1:]) if v is not None]
   if key not in found:found[key]=values
  if pi is not None and pref is None:
   pref=[v for v in (num(s) for s in cells[pi+1:]) if v is not None]
 if set(found)!=set(NAMES):raise RuntimeError("Missing municipalities: "+str(set(NAMES)-set(found)))
 return found,pref
def json_const(text,name):
 pos=text.index("const "+name+"=")+len("const "+name+"=")
 obj,size=json.JSONDecoder().raw_decode(text[pos:])
 return obj,pos,pos+size
ages={};vitals={}
for y,(_,ar,vr) in SOURCES.items():
 age_url,age_soup=source(y,ar);vital_url,vital_soup=source(y,vr)
 av,ap=extract(age_soup);vv,vp=extract(vital_soup)
 aa={};vn={}
 for name in NAMES:
  v=av[name]
  if len(v)<7:raise ValueError(f"{y}/{name}: age columns missing")
  total,young,work,old=map(intval,(v[0],v[1],v[3],v[5]))
  known=young+work+old
  if total<known or known<total*.70:raise ValueError(f"{y}/{name}: age invalid")
  aa[name]={"total_population":total,"age_0_14":young,"age_15_64":work,
   "age_65_plus":old,"age_unknown":total-known,
   "age_0_14_share":round(100*young/known,3),
   "age_15_64_share":round(100*work/known,3),
   "age_65_plus_share":round(100*old/known,3),"source":age_url}
  z=vv[name]
  if len(z)<5:raise ValueError(f"{y}/{name}: vital columns missing")
  change,natural,births,deaths,social=map(intval,z[:5])
  if births-deaths!=natural or natural+social!=change:
   raise ValueError(f"{y}/{name}: vital identity invalid {z[:5]}")
  vn[name]={"births":births,"deaths":deaths,"natural":natural,"social":social,"population_change":change,"source":vital_url}
 if ap is None or vp is None:raise ValueError(f"{y}: Prefecture total absent")
 for i,k in [(0,"total_population"),(1,"age_0_14"),(3,"age_15_64"),(5,"age_65_plus")]:
  if sum(v[k] for v in aa.values())!=intval(ap[i]):raise ValueError(f"{y}: age prefecture mismatch {k}")
 for i,k in [(0,"population_change"),(1,"natural"),(2,"births"),(3,"deaths"),(4,"social")]:
  if sum(v[k] for v in vn.values())!=intval(vp[i]):raise ValueError(f"{y}: vital prefecture mismatch {k}")
 ages[str(y)]=aa;vitals[str(y)]=vn
 print(y,"VALIDATED",flush=True)

index=ROOT/"index.html";s=index.read_text(encoding="utf-8")
data,a,b=json_const(s,"DATA")
extra,c,d=json_const(s,"EXTRA_DATA")
if data["years"]!=list(range(2015,2026)):raise ValueError("Unexpected app version")
assert set(data["municipalities"])==set(NAMES)
for y in range(2007,2015):
 ys=str(y);population={n:ages[ys][n]["total_population"] for n in NAMES}
 data["metrics"]["population"][ys]=population
 data["metrics"]["density"][ys]={n:round(population[n]/data["areas"][n],2) for n in NAMES}
 data["metrics"]["rate"][ys]={n:round((population[n]/data["metrics"]["population"]["2015"][n]-1)*100,5) for n in NAMES}
 data["metrics"]["net"][ys]={n:vitals[ys][n]["social"] for n in NAMES}
 data["roads"][ys]={}
 extra["age"][ys]=ages[ys];extra["natural"][ys]=vitals[ys]
data["years"]=list(range(2007,2026))
for key,tbl in data["metrics"].items():
 vals=[tbl[str(y)][n] for y in data["years"] for n in NAMES]
 data["ranges"][key]={"min":min(vals),"max":max(vals)}
s=s[:a]+json.dumps(data,ensure_ascii=False,separators=(",",":"))+s[b:]
_,c,d=json_const(s,"EXTRA_DATA")
s=s[:c]+json.dumps(extra,ensure_ascii=False,separators=(",",":"))+s[d:]
s=s.replace('id="slider" type="range" min="0" max="10" value="10"',
            'id="slider" type="range" min="0" max="18" value="18"')
s=s.replace("for(const y of DATA.years){const yr=String(y);",
            "for(const y of DATA.years){if(y<2015)continue;const yr=String(y);")
s=s.replace("2015〜2025年","2007〜2025年").replace("2015–2025年","2007–2025年")
s=s.replace("2015〜2024年","2007〜2024年")
links=" ".join(f'<a href="{BASE}/dataset/{SOURCES[y][0]}.html" target="_blank" rel="noopener">{y}年</a>' for y in SOURCES)
help_note=('<p><b>2007〜2014年の追加元データ：</b>'+links+
  '。各年の市町別「年齢（3区分）別人口」および「男女別人口動態」原表の公式プレビューを取得し、'
  '17市町の実数を県合計と照合して追加しました。2010年は国勢調査の確定値による再集計表です。'
  '県内市町間の個別OD（坂道）は2007〜2014年分を未収録としており、推計で作っていません。'
  '地図境界は2025年基準、人口密度は現在のアプリ採用面積を分母とします。</p>')
if "<h2>使い方 / データ出所</h2>" not in s:raise ValueError("Help section not found")
s=s.replace("<h2>使い方 / データ出所</h2>","<h2>使い方 / データ出所</h2>"+help_note,1)
index.write_text(s,encoding="utf-8")
for filename,content,columns in [
 ("kagawa_2007_2014_age.csv",ages,["total_population","age_0_14","age_15_64","age_65_plus","age_unknown","age_0_14_share","age_15_64_share","age_65_plus_share","source"]),
 ("kagawa_2007_2014_natural_social.csv",vitals,["births","deaths","natural","social","population_change","source"])]:
 with (ROOT/filename).open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=["year","municipality"]+columns);w.writeheader()
  for y in sorted(content):
   for n in NAMES:w.writerow({"year":y,"municipality":n,**content[y][n]})
print("DONE 2007–2014: 136 municipality-year observations per table",flush=True)
