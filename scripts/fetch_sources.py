#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json, re, urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'data'/'dashboard-data.json'
API='https://api.statbank.dk/v1'
UA='arbejdsstyrke-dashboard/1.0'

def norm(x):
    return re.sub(r'\s+',' ',str(x or '').strip().lower())

def info(table):
    req=urllib.request.Request(f'{API}/tableinfo/{table}?lang=da',headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)

def variable(meta, words):
    for v in meta['variables']:
        text=norm(v.get('text'))+' '+norm(v.get('id'))
        if any(norm(w) in text for w in words):return v
    raise RuntimeError(f'Variabel ikke fundet: {words}')

def value_code(v, labels, default_all=False):
    for val in v.get('values',[]):
        text=norm(val.get('text'))
        if any(norm(x)==text or norm(x) in text for x in labels):return str(val['id'])
    if default_all and v.get('values'):return str(v['values'][0]['id'])
    raise RuntimeError(f'Værdi ikke fundet i {v.get("text")}: {labels}')

def fetch_csv(table, selections):
    body={'table':table,'format':'CSV','lang':'da','variables':[{'code':c,'values':vals} for c,vals in selections.items()]}
    req=urllib.request.Request(f'{API}/data',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','User-Agent':UA},method='POST')
    with urllib.request.urlopen(req,timeout=90) as r:text=r.read().decode('utf-8-sig')
    return list(csv.DictReader(io.StringIO(text),delimiter=';'))

def num(v):
    t=str(v or '').strip().replace('\xa0','').replace(' ','')
    if not t or t in {'.','..','-'}:return None
    t=t.replace('.','').replace(',','.')
    try:return float(t)
    except:return None

def period_key(p):
    m=re.fullmatch(r'(\d{4})K([1-4])',str(p));return (int(m.group(1)),int(m.group(2))) if m else (9999,9)

def rows_aku100():
    meta=info('AKU100K'); status=variable(meta,['beskæftigelsesstatus']); time=variable(meta,['kvartal','tid'])
    rows=fetch_csv('AKU100K',{status['id']:['*'],time['id']:['*']})
    sc=list(rows[0]); status_col=sc[0]; time_col=sc[-2] if sc[-1].lower()=='indhold' else sc[-1]; value_col='INDHOLD' if 'INDHOLD' in sc else sc[-1]
    grouped={}
    for r in rows:
        p=r[time_col]; s=norm(r[status_col]); grouped.setdefault(p,{})[s]=num(r[value_col])
    labels=sorted(grouped,key=period_key)
    emp=[]; unemp=[]; outside=[]
    for p in labels:
        d=grouped[p]; emp.append(next((v for k,v in d.items() if k.startswith('beskæftigede')),None)); unemp.append(next((v for k,v in d.items() if 'aku-ledige' in k or k=='ledige'),None)); outside.append(next((v for k,v in d.items() if 'uden for arbejdsstyrken' in k),None))
    lf=[(a or 0)+(b or 0) if a is not None or b is not None else None for a,b in zip(emp,unemp)]
    pop=[(a or 0)+(b or 0)+(c or 0) if any(x is not None for x in (a,b,c)) else None for a,b,c in zip(emp,unemp,outside)]
    er=[round(a/b*100,2) if a is not None and b else None for a,b in zip(emp,pop)]
    pr=[round(a/b*100,2) if a is not None and b else None for a,b in zip(lf,pop)]
    ur=[round(a/b*100,2) if a is not None and b else None for a,b in zip(unemp,lf)]
    return meta,{'labels':labels,'employed':emp,'unemployed':unemp,'outside':outside,'labourForce':lf,'employmentRate':er,'participationRate':pr,'unemploymentRate':ur,'kpi':{'period':labels[-1],'labourForce':lf[-1],'employmentRate':er[-1]}}

def rows_age():
    meta=info('AKU110K'); status=variable(meta,['beskæftigelsesstatus']); age=variable(meta,['alder']); sex=variable(meta,['køn']); time=variable(meta,['kvartal','tid'])
    sex_all=value_code(sex,['i alt','total'],True)
    rows=fetch_csv('AKU110K',{status['id']:['*'],age['id']:['*'],sex['id']:[sex_all],time['id']:['*']})
    cols=list(rows[0]); value_col='INDHOLD' if 'INDHOLD' in cols else cols[-1]; status_col=cols[0]; age_col=cols[1]; time_col=next(c for c in cols if norm(c) in {'tid','kvartal'})
    g={}
    for r in rows:g.setdefault(r[time_col],{}).setdefault(r[age_col],{})[norm(r[status_col])]=num(r[value_col])
    labels=sorted(g,key=period_key); latest=labels[-1]
    def rate(p,a):
        d=g.get(p,{}).get(a,{}); e=next((v for k,v in d.items() if k.startswith('beskæftigede')),None); u=next((v for k,v in d.items() if 'aku-ledige' in k or k=='ledige'),None); o=next((v for k,v in d.items() if 'uden for arbejdsstyrken' in k),None); den=sum(x or 0 for x in (e,u,o));return round(e/den*100,2) if e is not None and den else None
    ages=[a for a in g[latest] if 'alt' not in norm(a)]
    rates=[rate(latest,a) for a in ages]
    def find_age(parts):return next((a for a in g[latest] if all(x in norm(a) for x in parts)),None)
    a55=find_age(['55','64']); a65=find_age(['65','74'])
    return meta,{'period':latest,'groups':ages,'rates':rates,'labels':labels,'rate5564':[rate(p,a55) for p in labels],'rate6574':[rate(p,a65) for p in labels],'kpi':{'rate6574':rate(latest,a65)}}

def rows_reserve():
    meta=info('AKU550K'); attach=variable(meta,['arbejdsmarkedstilknytning']); sex=variable(meta,['køn']); unit=variable(meta,['enhed']); time=variable(meta,['kvartal','tid'])
    sex_all=value_code(sex,['i alt','total'],True); unit_n=value_code(unit,['1.000 personer','1000 personer'],True)
    rows=fetch_csv('AKU550K',{attach['id']:['*'],sex['id']:[sex_all],unit['id']:[unit_n],time['id']:['*']})
    cols=list(rows[0]); val='INDHOLD' if 'INDHOLD' in cols else cols[-1]; a_col=cols[0]; t_col=next(c for c in cols if norm(c) in {'tid','kvartal'})
    g={}
    for r in rows:g.setdefault(r[t_col],{})[r[a_col]]=num(r[val])
    labels=sorted(g,key=period_key); latest=labels[-1]
    total_name=next((k for k in g[latest] if 'arbejdskraftreserve' in norm(k) and ('i alt' in norm(k) or norm(k)=='arbejdskraftreserven')),None)
    if not total_name: total_name=max(g[latest],key=lambda k:g[latest][k] or -1)
    mix=[{'label':k,'value':v} for k,v in g[latest].items() if k!=total_name and v is not None]
    return meta,{'period':latest,'labels':labels,'total':[g[p].get(total_name) for p in labels],'mix':mix,'kpi':{'total':g[latest].get(total_name)}}

def rows_projection():
    meta=info('FRDK126'); age=variable(meta,['alder']); time=variable(meta,['år','tid']); selections={age['id']:['*'],time['id']:['*']}
    for v in meta['variables']:
        if v['id'] in selections:continue
        selections[v['id']]=[value_code(v,['hele landet','i alt','total'],True)]
    rows=fetch_csv('FRDK126',selections); cols=list(rows[0]); val='INDHOLD' if 'INDHOLD' in cols else cols[-1]; age_col=next(c for c in cols if 'alder' in norm(c)); time_col=next(c for c in cols if norm(c) in {'tid','år'})
    g={}
    for r in rows:
        m=re.search(r'(\d+)',r[age_col]); y=re.search(r'(\d{4})',r[time_col]); v=num(r[val])
        if m and y and v is not None:g.setdefault(int(y.group(1)),{})[int(m.group(1))]=v
    years=[y for y in sorted(g) if y<=2035]
    def total(y,a,b):return sum(v for age,v in g[y].items() if a<=age<=b)
    return meta,{'labels':[str(y) for y in years],'age2064':[total(y,20,64) for y in years],'age2069':[total(y,20,69) for y in years],'age6574':[total(y,65,74) for y in years]}

def source(meta,table,period,unit,season):
    return {'state':'ok','source':'Danmarks Statistik','dataset':table,'latestPeriod':period,'sourceUpdated':meta.get('updated'),'unit':unit,'seasonalAdjustment':season}

def main():
    m1,main=rows_aku100();m2,age=rows_age();m3,res=rows_reserve();m4,proj=rows_projection();now=datetime.now(ZoneInfo('Europe/Copenhagen')).isoformat(timespec='seconds')
    sources={'AKU100K':source(m1,'AKU100K',main['labels'][-1],'1.000 personer','sæsonkorrigeret'),'AKU110K':source(m2,'AKU110K',age['period'],'1.000 personer','faktiske tal'),'AKU550K':source(m3,'AKU550K',res['period'],'1.000 personer','faktiske tal'),'FRDK126':source(m4,'FRDK126',proj['labels'][-1],'personer','ikke relevant')}
    data={'meta':{'checkedAt':now,'sourceStatus':sources,'updateStatus':{'state':'ok','successful':list(sources),'failed':[],'checkedAt':now}},'sections':{'main':main,'age':age,'reserve':res,'projection':proj}}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Opdateret',main['labels'][-1])
if __name__=='__main__':main()
