#!/usr/bin/env python3
import json
from pathlib import Path

base=Path(__file__).resolve().parents[1]
p=json.loads((base/'data'/'dashboard-data.json').read_text(encoding='utf-8'))
assert p['meta']['updateStatus']['state']=='ok'
for key in ('AKU100K','AKU110K','AKU550K','FRDK126'):
    assert p['meta']['sourceStatus'][key]['state']=='ok'
main=p['sections']['main']
assert len(main['labels'])>20
assert main['kpi']['period']==main['labels'][-1]
assert main['kpi']['labourForce'] is not None
assert len(p['sections']['age']['groups'])>=5
assert p['sections']['reserve']['kpi']['total'] is not None
assert p['sections']['projection']['labels']
for filename in ('index.html','style.css','script.js'):
    path=base/filename
    assert path.is_file() and path.stat().st_size>100
print('Dashboarddata bestod kvalitetskontrollen.')
