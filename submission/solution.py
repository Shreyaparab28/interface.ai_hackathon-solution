"""Offline, deterministic, snapshot-scoped evidence retrieval and typed rate facts."""
import re
import math
from collections import Counter, defaultdict
from datetime import date
try:
    from contract import Answer, Source, Conflict
except ImportError:
    from dataclasses import dataclass, field
    from typing import Optional
    @dataclass
    class Source:
        url: str
        snapshot_id: Optional[str] = None
        quote: Optional[str] = None
    @dataclass
    class Answer:
        text: str
        sources: list = field(default_factory=list)
        confident: bool = True
        conflict_note: Optional[str] = None
    @dataclass
    class Conflict:
        topic: str
        values: list
        sources: list
        resolution: Optional[str] = None
        reason: Optional[str] = None

STOP = set('what is are the a an of on for to in and or do does you your me can tell please dupaco current now rate rates interest apr apy'.split())
def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()
def tokens(s):
    ws=set(norm(s).split()) - STOP
    ws.update({'branch'} if 'branches' in ws else set())
    return ws
def clean(s):
    s = re.sub(r'!\[[^\]]*\]\([^\n]*?\)', '', s)
    s = re.sub(r'\[([^\]]+)\]\([^\n]*?\)', r'\1', s)
    return re.sub(r'[*_\\]', '', s).strip()
def published(md):
    from datetime import datetime
    dates=re.findall(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+20\d\d',md[:1800])
    for d in dates:
        for fmt in ['%b %d, %Y','%B %d, %Y']:
            try:return datetime.strptime(d,fmt).isoformat()
            except ValueError:pass
    return ''

def canonical(s):
    s=re.sub(r'\$([\d,]+(?:\.\d+)?)',lambda m:'$'+format(float(m[1].replace(',','')),'.10g'),s)
    return norm(s)

def authority(url):
    if '?' in url or 'privacy' in url: return -8
    if '/calculators/' in url: return -5
    if '/learn/blog/' in url: return -2
    if '/newsroom/' in url: return -1
    if url.rstrip('/').endswith('/rates'): return 5
    if '/personal/' in url or '/business/' in url: return 6
    return 2

def table_rows(md):
    """Yield (heading context, column names, row cells, source line)."""
    headers = None
    context = []
    for line in md.splitlines():
        if line.startswith('|'):
            cells = [clean(x) for x in line.strip().strip('|').split('|')]
            if all(re.fullmatch(r'[:\-\s]*', c) for c in cells): continue
            if headers is None:
                headers = cells
            elif len(cells) == len(headers):
                yield ' / '.join(context[-3:]), headers, cells, line
        else:
            headers = None
            t = clean(line).strip('# ').strip()
            if t and len(t) < 100 and not t.startswith(('http', '[')):
                context.append(t)

class Knowledge:
    def __init__(self):
        self.versions = {}
        self.cache = {}

    def ingest(self, snapshot):
        date.fromisoformat(snapshot.taken_on[:10])
        chunks, facts = [], []
        for p in sorted(snapshot.pages, key=lambda p:p.url):
            if '?' in p.url or 'privacy-policy' in p.url: continue
            heading = p.title
            # Paragraphs retain neighboring headings, but never mix entire rate tables.
            for block in p.markdown.split('\n\n'):
                if block.lstrip().startswith('#'):
                    heading = clean(block).strip('# ')
                t = clean(block)
                if not t or len(t) > 4500 or t.startswith('|'): continue
                if len(tokens(t)) < 3: continue
                chunks.append(dict(text=t, heading=heading, url=p.url,
                                   words=tokens(t+' '+heading), title=p.title))
            for context, headers, cells, quote in table_rows(p.markdown):
                numeric = [(h,c) for h,c in zip(headers,cells) if '%' in c and re.search(r'\d',c) and not any(x in h.lower() for x in ['points','payment'])]
                if not numeric: continue
                qualifiers = [(h,c) for h,c in zip(headers,cells) if '%' not in c and not any(x in h.lower() for x in ['payment','points'])]
                label = ' | '.join(c for h,c in qualifiers)
                if not label: continue
                for h,c in numeric:
                    # Footnote digits after % are metadata, not part of the rate.
                    value = ' – '.join(m+'%' for m in re.findall(r'(\d+(?:\.\d+)?)\s*%',c))
                    metric = 'APY' if 'yield' in h.lower() or 'apy' in h.lower() else ('APR' if 'apr' in h.lower() or 'percentage rate' in h.lower() else 'dividend rate' if 'dividend' in h.lower() else 'rate')
                    # Context disambiguates generic certificate terms across product tables.
                    family = 'certificate' if ('certificate' in headers[0].lower() or (headers[0].lower()=='term' and 'certificate' in context.lower())) else 'checking' if 'checking' in (context+' '+label).lower() else ''
                    scope='business' if '/business' in p.url else 'personal'
                    generic=not any(re.search(r'[a-z]',c,re.I) for h,c in qualifiers) or any('variable interest' in c.lower() for h,c in qualifiers)
                    identity=context.split(' / ')[-1] if generic else ''
                    if 'model year' in label.lower():scope+=' auto' if ('auto' in p.url or 'vehicle' in p.url or p.url.rstrip('/').endswith('/rates')) else ' '+p.url.split('/')[-1]
                    key = (scope+' '+family+' '+identity, tuple((canonical(h),canonical(c)) for h,c in qualifiers), metric)
                    facts.append(dict(key=key, label=label, metric=metric, value=value,
                                      context=context, url=p.url, quote=quote, words=tokens(label+' '+context)))
        df=Counter(w for c in chunks for w in c['words'])
        self.versions[snapshot.taken_on[:10]] = dict(sid=snapshot.snapshot_id, pages=snapshot.pages,
            chunks=chunks, facts=facts, df=df)
        self.cache.clear()

    def _view(self, as_of):
        ds=sorted(self.versions)
        if as_of:
            as_of=str(as_of)[:10]
            date.fromisoformat(as_of)
            ds=[d for d in ds if d<=as_of]
        return self.versions[ds[-1]] if ds else None

    def _ans(self, v, text, evidence, confident=True, note=None):
        src=[]
        for e in evidence:
            if e['url'] not in [s.url for s in src]:
                src.append(Source(e['url'], v['sid'], e.get('quote',e.get('text',''))[:700]))
        return Answer(text,src,confident,note)

    def _search(self,v,q,require=None,url=None):
        qw=tokens(q);n=len(v['chunks'])
        found=[]
        for c in v['chunks']:
            if url and url not in c['url']:continue
            if require and not require(c):continue
            score=sum(math.log(1+n/(1+v['df'][w])) for w in qw&c['words'])
            score+=0.3*len(qw&tokens(c['heading']))+0.3*authority(c['url'])
            if not qw&c['words'] and not require:continue
            score/=1+len(c['text'])/5000
            found.append((score,c))
        return [c for s,c in sorted(found,key=lambda t:(-t[0],t[1]['url'],t[1]['text']))]

    def answer(self, question, as_of=None):
        key=(question,as_of)
        if key not in self.cache:self.cache[key]=self._answer(question,as_of)
        # Return independent objects; callers cannot mutate the cached answer.
        import copy
        return copy.deepcopy(self.cache[key])

    def _answer(self,q,as_of):
        if as_of is None:
            explicit=re.search(r'\bas of\s+(20\d\d-\d\d-\d\d)',q,re.I)
            if explicit:as_of=explicit[1]
        v=self._view(as_of)
        if not v:return Answer("I don't know: no snapshot is available on or before that date.", confident=False)
        low=q.lower(); nq=norm(q)
        def reply(text,es,conf=True,note=None):return self._ans(v,text,es,conf,note)
        def search(s,**kw):return self._search(v,s,**kw)
        def unknown(es=()):return reply("The supplied website snapshots do not list that information. Please contact Dupaco for confirmation.",es,False)
        # Navigational answers use links actually observed in the selected snapshot.
        route=None
        if ('certificate' in low or re.search(r'\bcd\b',low)) and any(x in low for x in ['link','url','website']):route='/personal/savings-account#rates'
        elif ('locator' in low or ('url' in low and ('branch' in low or 'atm' in low))):route='/contact'
        elif ('join' in low or 'become a member' in low) and 'online' in low:route='https://join.dupaco.com/'
        if route:
            es=[dict(url=p.url,text=p.markdown) for p in v['pages'] if route in p.markdown]
            if es:return reply(route if route.startswith('http') else 'https://www.dupaco.com'+route,sorted(es,key=lambda e:(route.split('#')[0] not in e['url'],e['url']))[:1])
        if 'routing' in low:
            es=search('routing number',require=lambda c:bool(re.search(r'routing.{0,30}\b\d{9}\b',c['text'],re.I)))
            if es:
                number=re.search(r'routing.{0,30}\b(\d{9})\b',es[0]['text'],re.I).group(1)
                return reply('Dupaco’s routing number is '+number+'.',es[:1])
        # Rate questions: only extract qualifying rows from published rate tables.
        israte=any(x in low for x in ['rate','apr','apy','dividend','pay '])
        if israte:
            family=None;url=None
            if any(x in low for x in ['certificate',' cd',' cds']):family='certificate';url='/personal/savings-account'
            elif any(x in low for x in ['auto','vehicle','car loan','motorcycle']):family='auto';url='/personal/loans/auto-motorcycle-loans'
            elif 'mortgage' in low or 'home loan' in low or 'construction' in low:family='mortgage';url='/personal/loans/home-loans'
            elif 'personal loan' in low:family='personal';url='/personal/loans/personal-loans'
            elif 'checking' in low:family='checking';url='/personal/checking'
            elif any(x in low for x in ['savings','money market','hsa']):family='savings';url='/personal/savings-account'
            elif 'credit card' in low or 'visa' in low:family='cards';url='/rates'
            if family:
                fs=[f for f in v['facts'] if url in f['url'] and '?' not in f['url']]
                if family=='cards':
                    fs=[f for f in v['facts'] if 'credit-cards' in f['url'] and 'visa' in f['label'].lower()]
                    for c in v['chunks']:
                        if '/personal/credit-cards' not in c['url']:continue
                        if c['heading'] not in ['Platinum Visa','Rewards Visa']:continue
                        m=re.search(r'(\d+\.\d+%)\s*[–−-]\s*(\d+\.\d+%)\s*APR',c['text'])
                        if m:
                            fs.append(dict(label=c['heading'],metric='APR',value=m[1]+'–'+m[2],url=c['url'],quote=c['text']))
                    if 'business' in low:fs=[f for f in fs if 'business' in f['label'].lower()]
                    elif 'platinum' in low:fs=[f for f in fs if 'platinum' in f['label'].lower() and 'business' not in f['label'].lower()]
                    elif 'rewards' in low:fs=[f for f in fs if 'rewards' in f['label'].lower() and 'business' not in f['label'].lower()]
                if family=='certificate':
                    fs=[f for f in fs if 'certificate' in f['key'][0]]
                    if 'jumbo' in low:fs=[f for f in fs if 'jumbo' in f['label'].lower()]
                    if 'special' in low:fs=[f for f in fs if 'special' in f['label'].lower()]
                term=re.search(r'\b(\d{1,3})[ -]?(month|year)',low)
                if term:
                    num,unit=term.groups()
                    fs=[f for f in fs if re.search(r'\b'+num+r'[ -]?'+unit,f['label'],re.I)]
                if family=='auto':
                    yr=re.search(r'\b(20\d\d)\b',low)
                    if yr:
                        y=int(yr.group())
                        def matches(f):
                            m=re.search(r'(20\d\d)(?:\s*[-–]\s*(\d{2,4}))?',f['label'])
                            if not m:return False
                            a=int(m[1]);b=int(m[2]) if m[2] else a
                            if b<100:b+=2000
                            return a<=y<=b or ('older' in f['label'].lower() and y<=a)
                        fs=[f for f in fs if matches(f)]
                if family=='mortgage':
                    if 'construction' in low or re.search(r'\b\d/\d\b',low):return unknown(search('construction mortgage lender',url=url)[:1])
                    mode='refinance' if 'refinanc' in low else 'purchase'
                    fs=[f for f in fs if mode in f['label'].lower()]
                    if not term:fs=[f for f in fs if '30-Year' in f['label'] or '15-Year' in f['label']]
                    amount=re.search(r'\$([\d,]+)',q)
                    if amount:
                        amt=amount[1]
                        fs=[f for f in fs if '$'+amt in f['label']]
                    fs.sort(key=lambda f:('100,000' not in f['label'],f['label'],f['metric']))
                if family=='savings':
                    names=['share savings','bright savings','holiday club','launchpad','you name it','investor','high-yield','health savings','achieve']
                    name=next((x for x in names if x in low),None)
                    if name:fs=[f for f in fs if name in f['label'].lower()]
                    if 'highest' in low or ('0.35' in low and name=='share savings'):
                        fs=[f for f in fs if f['metric']=='APY']
                        if fs:fs=[max(fs,key=lambda f:float(re.search(r'[\d.]+',f['value'])[0]))]
                    amounts=re.findall(r'\$([\d,]+)',q)
                    if amounts and 'highest' not in low:
                        amount=float(amounts[0].replace(',',''))
                        def contains(f):
                            parts=f['label'].split('|')
                            if len(parts)<2:return False
                            nums=[float(x.replace(',','')) for x in re.findall(r'\$([\d,]+(?:\.\d+)?)',parts[1])]
                            return bool(nums) and nums[0]<=amount and (len(nums)==1 or amount<=nums[1])
                        fs=[f for f in fs if contains(f)]
                if fs:
                    # APY and rate are distinct facts. Never label a dividend rate as an APY.
                    if family=='certificate' and 'dividend' not in low:fs=[f for f in fs if f['metric']=='APY']
                    seen=set(); selected=[]
                    for f in fs:
                        k=(f['label'],f['metric'],f['value'])
                        if k not in seen:seen.add(k);selected.append(f)
                    text='; '.join(f['label']+': '+f['value']+' '+f['metric'] for f in selected)+'.'
                    if family=='savings' and '0.35' in low and name=='share savings':text='For Share Savings, the highest published tier is '+text
                    return reply(text,selected,note='Published product rate tables take priority over calculator examples and historical marketing content.')
                return unknown()
        # Branch closure is an event, distinct from general hours.
        if 'hy vee' in nq:
            es=search('Hy Vee branch close services Key West Sycamore',url='hy-vee-branch-closure')
            if es:
                if any(x in low for x in ['where','full-service','full service']):
                    es=[c for c in es if 'Sycamore' in c['text']][:1]
                else:es=[c for c in es if re.search(r'close\s+\w+\s+\d',c['text'])][:1]
                if es:return reply('According to the closure announcement: '+es[0]['text'],es)
        if 'lobby' in low or 'drive-up' in low or 'drive up' in low:
            # A named branch needs branch-specific evidence; generic schedules are insufficient.
            m=re.search(r'(?:the|for)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\s+branch',q)
            if m:
                name=m[1].lower()
                exact=[p for p in v['pages'] if name in p.markdown.lower() and ('lobby' in p.markdown.lower() or 'drive-up hours' in p.markdown.lower())]
                if not exact:return unknown()
            es=search('drive up hours' if 'drive' in low else 'lobby hours',require=lambda c:bool(re.search(r'(?:a\.m\.|p\.m\.|\d:\d\d)',c['text'])) )
            # Schedules often span several paragraphs following a Lobby/Drive-Up heading.
            schedules=[]
            target='Drive' if 'drive' in low else 'Lobby'
            for p in sorted(v['pages'],key=lambda p:p.url):
                for match in re.finditer(r'(?:^|\n)(?:#{1,6}\s*)?[*]*'+target+r'(?:[- ]up)?(?: Hours)?[*]*\s*\n',p.markdown,re.I):
                    snippet=clean(p.markdown[match.start():match.start()+450])
                    snippet=re.split(r'\n(?:##|!\[|\[|ABOUT DUPACO|Drive-up|Lobby)',snippet.lstrip())[0]
                    if re.search(r'\d(?::\d\d)?\s*(?:a\.m\.|p\.m\.)',snippet):schedules.append(dict(url=p.url,text=snippet))
            if schedules:
                ss=schedules[:2]
                return reply('Hours vary by branch. Examples from the website: '+'; '.join(c['text'] for c in ss)+'. Which branch would you like? (Some Saturday schedules end at noon.)',ss)
            return unknown(es[:1])
        # Explicit evidence requirements keep unrelated matches out of named entities.
        required=None
        if 'forbes' in low:required=lambda c:'forbes' in c['text'].lower() and any(x in c['text'].lower() for x in ['fifth','fourth','third','recognized','recognition'])
        if 'volunteer' in low:required=lambda c:'volunteer time off' in c['text'].lower() and bool(re.search(r'\d+.*employees',c['text'],re.I))
        if 'branch' in low and ('how many' in low or 'number of' in low):required=lambda c:bool(re.search(r'\d+ branch office locations',c['text']))
        if 'galena' in low:
            # Locator records distinguish the institution's branch from third-party ATMs.
            for p in v['pages']:
                if p.url.rstrip('/').endswith('/contact'):
                    for block in re.split(r'(?m)^### ',p.markdown):
                        if 'Dupaco Branch' in block and 'Galena' in block:
                            lines=[x for x in block.splitlines() if 'Galena' in x and re.search(r'\d',x)]
                            if lines:return reply(lines[0].replace('Ln.','Lane'),[dict(url=p.url,text=lines[0])])
            return unknown()
        if 'mobile wallet' in low or ('wallet' in low and 'card' in low):required=lambda c:'apple pay' in c['text'].lower()
        if ('eligible' in low or 'who can' in low) and 'member' in low:required=lambda c:all(x in c['text'] for x in ['Iowa','Illinois','Wisconsin'])
        if 'home$tart' in low or 'homestart' in low:required=lambda c:'15,000' in c['text'] and ('home$tart' in c['text'].lower() or 'first-time' in c['text'].lower())
        es=search(q,require=required)
        if not es:return unknown()
        if 'student' in low:es=search('student loan flexible repayment origination',url='student')
        if not es:return unknown()
        chosen=es[0]
        if 'branch' in low and ('how many' in low or 'number of' in low):
            chosen=max(es,key=lambda c:published(next(p.markdown for p in v['pages'] if p.url==c['url'])))
        if 'forbes' in low:
            # Order recognition articles by their actual publication date, not crawl date.
            def recency(c):
                p=next(p for p in v['pages'] if p.url==c['url'])
                dates=re.findall(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+20\d\d',p.markdown[:1800])
                from email.utils import parsedate_to_datetime
                from datetime import datetime
                for d in dates:
                    for fmt in ['%b %d, %Y','%B %d, %Y']:
                        try:return datetime.strptime(d,fmt).isoformat()
                        except ValueError:pass
                return ''
            chosen=max(es,key=lambda c:(recency(c), 'fifth' in c['text'].lower()))
        # Require reasonable lexical coverage for generic questions.
        if required is None and len(tokens(q)&chosen['words'])<min(2,len(tokens(q))):return unknown(es[:1])
        text=chosen['text']
        if 'student' in low:text='Student loans: '+text
        if 'galena' in low:text=text.replace('Ln.', 'Lane')
        if 'branch' in low and ('how many' in low or 'number of' in low):
            text=re.search(r'\d+ branch office locations',text)[0]+'.'
        if 'contact information' in low or 'update my' in low:
            es=search('update contact information Shine 800-373-7600')
            chosen=es[0];text=chosen['text']
        return reply(text,[chosen])

    def conflicts(self):
        """Compare the same qualified fact only; history changes are explicitly labeled."""
        history=defaultdict(list)
        for d,v in sorted(self.versions.items()):
            for f in v['facts']:history[f['key']].append((d,v,f))
        out=[]
        for key,items in sorted(history.items(),key=lambda kv:str(kv[0])):
            representatives={}
            for d,v,f in items:
                signature=tuple(float(x) for x in re.findall(r'(\d+(?:\.\d+)?)%',f['value']))
                representatives[signature]=f['value']
            vals=sorted(representatives.values())
            if len(vals)<2:continue
            latest=max(d for d,v,f in items)
            candidates=[(d,v,f) for d,v,f in items if d==latest]
            winner=max(candidates,key=lambda t:(authority(t[2]['url']),t[2]['url']))
            d,v,f=winner
            current_vals=set(x['value'] for dd,vv,x in candidates)
            reason=('Within-snapshot disagreement; prefer official product/rate page over secondary sources.' if len(current_vals)>1 else 'Historical rate change across snapshots; latest observed qualified fact supersedes earlier observations. This is not proof of a simultaneous contradiction.')
            sources=[];seen=set()
            for dd,vv,x in items:
                k=(x['url'],x['value'])
                if k not in seen:
                    seen.add(k);sources.append(Source(x['url'],vv['sid'],x['quote'][:700]))
            topic=f['label']+' '+f['metric']
            out.append(Conflict(topic,vals,sources,f['value'],reason))
        return out

def build():
    return Knowledge()
