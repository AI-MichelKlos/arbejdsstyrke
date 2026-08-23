#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json, re, urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import jobindsats_api as ji

BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'data'/'dashboard-data.json'
API='https://api.statbank.dk/v1'
UA='arbejdsstyrke-dashboard/2.0'

def norm(x):return re.sub(r'\s+',' ',str(x or '').strip().lower())
def info(table):
    req=urllib.request.Request(f'{API}/tableinfo/{table}?lang=da',headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
def variable(meta,words):
    for v in meta['variables']:
        text=norm(v.get('text'))+' '+norm(v.get('id'))
        if any(norm(w) in text for w in words):return v
    raise RuntimeError(f'Variabel ikke fundet: {words}')
def valcode(v,labels,default_all=False):
    for val in v.get('values',[]):
        text=norm(val.get('text'))
        if any(norm(x)==text or norm(x) in text for x in labels):return str(val['id'])
    if default_all and v.get('values'):return str(v['values'][0]['id'])
    raise RuntimeError(f'Værdi ikke fundet i {v.get("text")}: {labels}')
def fetch_csv(table,selections):
    body={'table':table,'format':'CSV','lang':'da','variables':[{'code':c,'values':vals} for c,vals in selections.items()]}
    req=urllib.request.Request(f'{API}/data',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','User-Agent':UA},method='POST')
    with urllib.request.urlopen(req,timeout=90) as r:text=r.read().decode('utf-8-sig')
    return list(csv.DictReader(io.StringIO(text),delimiter=';'))
def num(v):
    t=str(v or '').strip().replace('\xa0','').replace(' ','')
    if not t or t in {'.','..','-'}:return None
    if ',' in t:t=t.replace('.','').replace(',','.')
    try:return float(t)
    except:return None
def period_key(p):
    m=re.fullmatch(r'(\d{4})K([1-4])',str(p));
    if m:return (int(m.group(1)),int(m.group(2)))
    m=re.fullmatch(r'(\d{4})M(\d{2})',str(p));
    if m:return (int(m.group(1)),int(m.group(2)))
    m=re.search(r'(\d{4})',str(p));return (int(m.group(1)),0) if m else (9999,99)
def value_col(rows):
    cols=list(rows[0]);return 'INDHOLD' if 'INDHOLD' in cols else cols[-1]

def aku_current():
    meta=info('AKU100K');status=variable(meta,['beskæftigelsesstatus']);time=variable(meta,['kvartal','tid'])
    rows=fetch_csv('AKU100K',{status['id']:['*'],time['id']:['*']});cols=list(rows[0]);sc=cols[0];tc=next(c for c in cols if norm(c) in {'tid','kvartal'});vc=value_col(rows)
    g={}
    for r in rows:g.setdefault(r[tc],{})[norm(r[sc])]=num(r[vc])
    labels=sorted(g,key=period_key);emp=[];unemp=[];outside=[]
    for p in labels:
        d=g[p];emp.append(next((v for k,v in d.items() if k.startswith('beskæftigede')),None));unemp.append(next((v for k,v in d.items() if 'aku-ledige' in k or k=='ledige'),None));outside.append(next((v for k,v in d.items() if 'uden for arbejdsstyrken' in k),None))
    force=[(a or 0)+(b or 0) if a is not None or b is not None else None for a,b in zip(emp,unemp)]
    return meta,{'labels':labels,'employed':emp,'unemployed':unemp,'outside':outside,'labourForce':force,'kpi':{'period':labels[-1],'labourForce':force[-1],'employed':emp[-1]}}

def ras():
    meta=info('RAS200');area=variable(meta,['område']);origin=variable(meta,['herkomst']);age=variable(meta,['alder']);sex=variable(meta,['køn']);freq=variable(meta,['frekvens']);time=variable(meta,['år','tid'])
    sel={area['id']:[valcode(area,['hele landet','danmark'],True)],origin['id']:[valcode(origin,['i alt','total'],True)],age['id']:['*'],sex['id']:[valcode(sex,['i alt','total'],True)],freq['id']:['*'],time['id']:['*']}
    rows=fetch_csv('RAS200',sel);cols=list(rows[0]);ac=next(c for c in cols if 'alder' in norm(c));fc=next(c for c in cols if 'frekvens' in norm(c));tc=next(c for c in cols if norm(c) in {'tid','år'});vc=value_col(rows)
    g={}
    for r in rows:g.setdefault(r[tc],{}).setdefault(r[ac],{})[norm(r[fc])]=num(r[vc])
    years=sorted(g,key=period_key);latest=years[-1];ages=[a for a in g[latest] if 'alt' not in norm(a)]
    def emp(p,a):return next((v for k,v in g.get(p,{}).get(a,{}).items() if 'beskæftigelsesfrekvens' in k),None)
    def part(p,a):return next((v for k,v in g.get(p,{}).get(a,{}).items() if 'erhvervsfrekvens' in k),None)
    age_items=[{'label':a,'employmentRate':emp(latest,a),'participationRate':part(latest,a)} for a in ages]
    focus=[]
    for a in ages:
        n=norm(a)
        if any(x in n for x in ('55','60','65')):focus.append({'label':a,'values':[emp(y,a) for y in years]})
    total_age=next((a for a in g[latest] if '16-66' in norm(a) or 'i alt' in norm(a)),None)
    return meta,{'period':latest,'ageItems':age_items,'labels':years,'focus':focus,'kpi':{'employmentRate':emp(latest,total_age) if total_age else None,'participationRate':part(latest,total_age) if total_age else None}}

def employees():
    meta=info('LBESK104');sector=variable(meta,['sektor']);time=variable(meta,['måned','tid']);total=valcode(sector,['i alt','alle sektorer','sektorer i alt'],True)
    rows=fetch_csv('LBESK104',{sector['id']:[total],time['id']:['*']});cols=list(rows[0]);tc=next(c for c in cols if norm(c) in {'tid','måned'});vc=value_col(rows);labels=[];values=[]
    for r in rows:labels.append(r[tc]);values.append(num(r[vc]))
    order=sorted(range(len(labels)),key=lambda i:period_key(labels[i]));labels=[labels[i] for i in order];values=[values[i] for i in order]
    return meta,{'labels':labels,'values':values,'kpi':{'period':labels[-1],'value':values[-1]}}

def projection():
    meta=info('FRDK126');age=variable(meta,['alder']);time=variable(meta,['år','tid']);sel={age['id']:['*'],time['id']:['*']}
    for v in meta['variables']:
        if v['id'] not in sel:sel[v['id']]=[valcode(v,['hele landet','i alt','total'],True)]
    rows=fetch_csv('FRDK126',sel);cols=list(rows[0]);vc=value_col(rows);ac=next(c for c in cols if 'alder' in norm(c));tc=next(c for c in cols if norm(c) in {'tid','år'});g={}
    for r in rows:
        m=re.search(r'(\d+)',r[ac]);y=re.search(r'(\d{4})',r[tc]);v=num(r[vc])
        if m and y and v is not None:g.setdefault(int(y.group(1)),{})[int(m.group(1))]=v
    years=[y for y in sorted(g) if y<=2035];tot=lambda y,a,b:sum(v for ag,v in g[y].items() if a<=ag<=b)
    return meta,{'labels':[str(y) for y in years],'age2064':[tot(y,20,64) for y in years],'age2069':[tot(y,20,69) for y in years],'age6574':[tot(y,65,74) for y in years]}

def senior_level(age_h):
    levels={}
    for d in ji.walk(age_h):
        lid=d.get('level_id')
        if isinstance(lid,str):levels.setdefault(lid,set()).update(str(x.get('value_id')) for x in ji.walk(d) if isinstance(x.get('value_id'),str))
    if not levels:return None
    return max(levels,key=lambda k:len(levels[k]))
def seniors():
    tables=ji.get('tables',{'format':'json'});table=ji.find_table(tables,['arbejdsmarkedsstatus for seniorer']);tid=str(table['table_id']);spec=ji.get(f'table/{tid}',{'format':'json'})
    geo=ji.find_hierarchy(spec,['område','geografi','kommune'],('_hele_landet','_nykom'));age=ji.find_hierarchy(spec,['alder']);status=ji.find_hierarchy(spec,['arbejdsmarkedsstatus','status']);alevel=senior_level(age)
    params={'mgroup.*':'*','period.M':'latest:1',f'hierarchy.{geo["hierarchy_id"]}':ji.country_value(geo),f'hierarchy.{age["hierarchy_id"]}':f'level:{alevel}' if alevel else '*',f'hierarchy.{status["hierarchy_id"]}':'*','format':'json'}
    rows=ji.records(ji.get(f'data/{tid}',params));agec=ji.best_col(rows,['alder'],distinct=True);statusc=ji.best_col(rows,['arbejdsmarkedsstatus','status'],distinct=True);pctc=ji.best_col(rows,['procent'],exclude=['grad']);pc=ji.best_col(rows,['periode'])
    g={};period=max((str(r.get(pc)) for r in rows),key=period_key)
    for r in rows:
        if str(r.get(pc))!=period:continue
        st=ji.norm(r.get(statusc));a=str(r.get(agec) or '').strip();v=ji.num(r.get(pctc))
        if a and v is not None and ('loenmodtagerbeskaeftigelse i alt' in st or st=='loenmodtagerbeskaeftigelse'):g[a]=float(v)*100 if abs(float(v))<=1 else float(v)
    items=[]
    for a,v in g.items():
        m=re.search(r'(?<!\d)(\d{2})(?!\d)',a)
        if m and int(m.group(1))>=55:items.append({'age':int(m.group(1)),'label':a,'employmentShare':round(v,2)})
    items.sort(key=lambda x:x['age'])
    if len(items)<8:raise RuntimeError(f'Seniormålingen gav kun {len(items)} et-årige aldersgrupper')
    return tid,{'period':period,'items':items}

def src(meta,table,period,unit,season):return {'state':'ok','source':'Danmarks Statistik','dataset':table,'latestPeriod':period,'sourceUpdated':meta.get('updated'),'unit':unit,'seasonalAdjustment':season}
def main():
    m_aku,aku=aku_current();m_ras,rasd=ras();m_emp,empl=employees();m_proj,proj=projection();sid,sen=seniors();now=datetime.now(ZoneInfo('Europe/Copenhagen')).isoformat(timespec='seconds')
    sources={'AKU100K':src(m_aku,'AKU100K',aku['labels'][-1],'1.000 personer','sæsonkorrigeret'),'RAS200':src(m_ras,'RAS200',rasd['period'],'pct.','ikke relevant'),'LBESK104':src(m_emp,'LBESK104',empl['labels'][-1],'personer','sæsonkorrigeret'),'FRDK126':src(m_proj,'FRDK126',proj['labels'][-1],'personer','ikke relevant'),'seniorer':{'state':'ok','source':'Jobindsats.dk / STAR','dataset':sid,'latestPeriod':sen['period'],'unit':'pct.','seasonalAdjustment':'ikke relevant'}}
    data={'meta':{'checkedAt':now,'sourceStatus':sources,'updateStatus':{'state':'ok','successful':list(sources),'failed':[],'checkedAt':now}},'sections':{'aku':aku,'ras':rasd,'employees':empl,'projection':proj,'seniors':sen}}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('RAS',rasd['period'],'AKU',aku['labels'][-1],'seniorer',sen['period'])
if __name__=='__main__':main()
