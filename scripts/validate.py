#!/usr/bin/env python3
import json
from pathlib import Path
base=Path(__file__).resolve().parents[1]
p=json.loads((base/'data'/'dashboard-data.json').read_text(encoding='utf-8'))
assert p['meta']['updateStatus']['state'] in {'ok','partial'}
for key in ('AKU100K','RAS200','LBESK104','FRDK126'):
    assert p['meta']['sourceStatus'][key]['state']=='ok'
assert p['meta']['sourceStatus']['seniorer']['state'] in {'ok','missing'}
aku=p['sections']['aku'];ras=p['sections']['ras'];emp=p['sections']['employees'];sen=p['sections']['seniors']
assert len(aku['labels'])>20 and aku['kpi']['period']==aku['labels'][-1]
assert ras['period'] and len(ras['ageItems'])>=8
assert any(x.get('employmentRate') is not None for x in ras['ageItems'])
assert len(emp['labels'])>50 and emp['kpi']['period']==emp['labels'][-1] and emp['kpi']['value'] is not None
if p['meta']['sourceStatus']['seniorer']['state']=='ok':
    assert len(sen['items'])>=8 and sen['period']
assert p['sections']['projection']['labels']
for filename in ('index.html','style.css','script.js'):
    path=base/filename;assert path.is_file() and path.stat().st_size>100
print('Dashboarddata bestod kvalitetskontrollen.')
