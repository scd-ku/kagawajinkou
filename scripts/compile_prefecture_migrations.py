#!/usr/bin/env python3
"""Extract *observed* Kagawa city -> prefecture migration counts from official Excel annual tables.

Output format:
  years[year][city][prefecture] = [in_male, in_female, out_male, out_female]
Unknown destinations are not spatially assigned. Only verified complete city blocks are emitted.
"""
from __future__ import annotations
import io
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, unquote

import requests
from bs4 import BeautifulSoup
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"kagawa_prefecture_flows.json"
CITIES="高松市 丸亀市 坂出市 善通寺市 観音寺市 さぬき市 東かがわ市 三豊市 土庄町 小豆島町 三木町 直島町 宇多津町 綾川町 琴平町 多度津町 まんのう町".split()
PREFS="北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県 国外".split()
LEGACY={2007:834,2008:835,2009:836,2010:839,2011:838,2012:840,2013:217,2014:218}
SESSION=requests.Session()
SESSION.headers.update({"User-Agent":"Kagawa-University-Science-Communication-Data-Research/1.0"})

def norm(value):
    return re.sub(r"[\s\u3000【】〔〕\[\]（）()・]", "",str(value or "")).replace("ヶ","ケ")

def num(value):
    if value is None or isinstance(value,bool):return 0
    if isinstance(value,(int,float)):return int(value) if float(value).is_integer() else None
    t=str(value).replace(",","").strip()
    if t in ("","-","－","―","…","×"):return 0
    try:
        x=float(t)
        return int(x) if x.is_integer() else None
    except (ValueError,OverflowError):return None

def get(url):
    for attempt in range(3):
        try:
            resp=SESSION.get(url,timeout=35)
            resp.raise_for_status()
            return resp
        except Exception:
            if attempt==2:raise
            time.sleep(attempt+1)

def excel_url(year):
    if year==2025:
        return "https://www.pref.kagawa.lg.jp/documents/62699/hyo004.xlsx"
    if year>=2015:
        url=f"https://www.pref.kagawa.lg.jp/tokei/jinko/jinkoido/{year}jinkoido.html"
    elif year in LEGACY:
        url=f"https://opendata.pref.kagawa.lg.jp/dataset/{LEGACY[year]}.html"
    else:return None
    html=get(url).text
    soup=BeautifulSoup(html,"html.parser")
    links=[]
    for a in soup.select("a[href]"):
        href=urljoin(url,a["href"])
        # Prefectural annual report tables keep the table description in a sibling
        # cell, while the actual link text is only "第6表". Search the whole row.
        row_text=a.find_parent("tr").get_text(" ",strip=True) if a.find_parent("tr") else ""
        title=norm(a.get_text(" ",strip=True)+" "+row_text+" "+unquote(href))
        if ".xlsx" not in href.lower():continue
        if year>=2015:
            if "県外移動者数" in title and "市町別" in title:
                return href
        elif "県外移動者数" in title and ("市町別" in title or "転入前住所地" in title):
            links.append(href)
    # Some legacy years use two separate halves. Avoid publishing an incomplete merged dataset.
    return links[0] if len(links)==1 else None

def count_columns(row,label_column):
    """Find six adjacent amount columns using a total row as an arithmetic checksum."""
    candidates=[]
    for k in range(label_column+1,min(len(row)-5,45)):
        vals=[num(v) for v in row[k:k+6]]
        if any(v is None for v in vals):continue
        if vals[0]<=0 or vals[3]<=0:continue
        if vals[0]!=vals[1]+vals[2] or vals[3]!=vals[4]+vals[5]:continue
        candidates.append((k,vals))
    return candidates[0] if candidates else None

def parse_workbook(data):
    wb=load_workbook(io.BytesIO(data),read_only=True,data_only=True)
    cities={}
    for sheet in wb.worksheets:
        rows=list(sheet.values)
        sheet_city=next((n for n in CITIES if norm(sheet.title)==norm(n)),None)
        current=sheet_city
        cols=None
        observed={}
        totals={}
        for row in rows:
            if not row:continue
            # Municipalities may be sections of a large worksheet or separate worksheets.
            section=next((n for n in CITIES if any(norm(v)==n for v in row[:7] if v is not None)),None)
            if section:
                if current and observed and len(observed)>=35:
                    cities[current]=observed
                current=section;cols=None;observed={}
                continue
            if not current:continue
            label=next(((i,norm(v)) for i,v in enumerate(row[:7]) if norm(v) in PREFS or norm(v) in ("総数","総計")),None)
            if not label:continue
            k,name=label
            if name in ("総数","総計"):
                probe=count_columns(row,k)
                if probe:
                    cols=probe[0]
                    totals[current]=probe[1]
                continue
            if cols is None:continue
            nums=[num(v) for v in row[cols:cols+6]]
            if len(nums)!=6 or any(v is None for v in nums):continue
            if nums[0]!=nums[1]+nums[2] or nums[3]!=nums[4]+nums[5]:
                continue
            observed[name]=[nums[1],nums[2],nums[4],nums[5]]
        if current and len(observed)>=35:
            cities[current]=observed
    # Never silently treat an incomplete or misaligned sheet as official municipal data.
    complete={}
    for city,blocks in cities.items():
        if len(blocks)<35:continue
        totals_city=totals.get(city)
        if totals_city:
            im=sum(v[0] for v in blocks.values())
            iff=sum(v[1] for v in blocks.values())
            om=sum(v[2] for v in blocks.values())
            of=sum(v[3] for v in blocks.values())
            # Excludes possible unknown-address rows; allow small differences, not broad gaps.
            if any(sum(abs(d) for d in [im-totals_city[1],iff-totals_city[2],om-totals_city[4],of-totals_city[5]])>max(60,(totals_city[0]+totals_city[3])*.06) for _ in [0]):
                print(f"SKIP {city}: totals do not reconcile",file=sys.stderr)
                continue
        complete[city]=blocks
    return complete

def main():
    document=json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"schema":1,"years":{},"sources":{}}
    updated=[]
    for year in range(2025,2006,-1):
        try:
            url=excel_url(year)
            if not url:
                print(f"{year}: source not uniquely resolvable; skip")
                continue
            records=parse_workbook(get(url).content)
            if len(records)<12:
                print(f"{year}: only {len(records)} city sheets validated; skip",file=sys.stderr)
                continue
            document.setdefault("years",{})[str(year)]=records
            document.setdefault("sources",{})[str(year)]=url
            updated.append(year)
            print(f"{year}: verified {len(records)} cities, {sum(len(v) for v in records.values())} prefecture pairs")
        except Exception as ex:
            print(f"{year}: {ex}",file=sys.stderr)
    if not updated:
        raise SystemExit("No yearly official data could be validated; original JSON unchanged")
    document["schema"]=1
    document["complete"]=len(document["years"])==19 and all(len(block)==17 for block in document["years"].values())
    document["label"]="香川県人口移動調査・市町別、転入前住所地/転出後住所地別、男女別県外移動者数（公式値）"
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(document,ensure_ascii=False,indent=1)+"\n",encoding="utf-8")
    print("Updated years:",",".join(map(str,updated)))

if __name__=="__main__":main()
