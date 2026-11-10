"""Run from the kit root: python submission/ask.py 'question' [--as-of YYYY-MM-DD]."""
import argparse
import json
import sys
from pathlib import Path
from dataclasses import asdict
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root/'harness'))
from run_eval import load_snapshots
from solution import build
p=argparse.ArgumentParser()
p.add_argument('question',nargs='?')
p.add_argument('--as-of')
p.add_argument('--snapshots',type=Path,default=root/'snapshots')
p.add_argument('--conflicts',action='store_true')
a=p.parse_args()
k=build()
for s in load_snapshots(a.snapshots):k.ingest(s)
if a.conflicts:result=[asdict(c) for c in k.conflicts()]
elif a.question:result=asdict(k.answer(a.question,a.as_of))
else:p.error('provide a question or --conflicts')
print(json.dumps(result,indent=2,ensure_ascii=False))
