#!/usr/bin/env python3
from __future__ import annotations
import json, urllib.request
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
DATA=BASE/'data'/'dashboard-data.json'
URL='https://raw.githubusercontent.com/AI-MichelKlos/Dashboard/main/data/senior-status.json'

def main():
    req=urllib.request.Request(URL,headers={'User-Agent':'arbejdsstyrke-dashboard/2.1','Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=60) as response:
        senior=json.load(response)
    items=senior.get('items') or []
    period=senior.get('period')
    meta=senior.get('meta') or {}
    if not period or len(items)<8:
        raise RuntimeError('Det centrale seniorfeed mangler periode eller 1-årige aldersgrupper')
    data=json.loads(DATA.read_text(encoding='utf-8'))
    data['sections']['seniors']={'period':period,'items':items}
    data['meta']['sourceStatus']['seniorer']={
        'state':'ok','source':'Jobindsats.dk / STAR','dataset':meta.get('dataset','Arbejdsmarkedsstatus for seniorer'),
        'latestPeriod':period,'unit':'pct.','seasonalAdjustment':'ikke relevant','via':'AI-MichelKlos/Dashboard/data/senior-status.json'
    }
    successful=[x for x in data['meta']['updateStatus'].get('successful',[]) if x!='seniorer']
    successful.append('seniorer')
    data['meta']['updateStatus']['successful']=successful
    data['meta']['updateStatus']['failed']=[x for x in data['meta']['updateStatus'].get('failed',[]) if not str(x).startswith('seniorer:')]
    data['meta']['updateStatus']['state']='ok' if not data['meta']['updateStatus']['failed'] else 'partial'
    DATA.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Indlæste centralt seniorfeed',period,len(items))
if __name__=='__main__':main()
