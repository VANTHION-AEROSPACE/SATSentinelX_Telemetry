"""Six-case actual Yamcs equivalence replay.

Uses the pre-existing six local Yamcs-parameter streams only as the exact
source packet list, sends them through the configured UDP Parameter Data Link,
retrieves the resulting values from Yamcs parameter history, and evaluates
the immutable Detector v1 without modifying any frozen research artifact.
"""
from __future__ import annotations
import csv, hashlib, importlib.util, json, math, socket, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]; YAMCS=ROOT/'yamcs'; OUT=HERE/'outputs'; BASE=YAMCS/'outputs'; CASES=YAMCS/'cases'/'replay_cases.json'
V1=ROOT/'inspection'/'class3_detector_v1.py'; HARNESS=ROOT/'inspection'/'evaluate_class3_detector_v1.py'; URL='http://localhost:8091'; HOST='127.0.0.1'; PORT=11016; ATOL=1e-12; RTOL=1e-12; CONTEXT=3600
READINESS=[]

def load(p,n):
    s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def sha(p):
    h=hashlib.sha256();
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def api(path, timeout=180):
    with urlopen(Request(URL+path,headers={'Accept':'application/json'}),timeout=timeout) as r: return json.loads(r.read().decode())
def iso(ts): return pd.Timestamp(ts).tz_localize('UTC').isoformat(timespec='milliseconds').replace('+00:00','Z')
def health():
    inst=api('/api/instances'); row=next(x for x in inst['instances'] if x['name']=='satsentinel_x')
    links=api('/api/links/satsentinel_x').get('links',api('/api/links/satsentinel_x').get('link',[])); link=next(x for x in links if x['name']=='esa_pp_realtime')
    procs=api('/api/processors/satsentinel_x/realtime');
    if row.get('state')!='RUNNING' or link.get('status')!='OK' or procs.get('state') not in ('RUNNING','RUNNING_REPLAY'): raise RuntimeError({'instance':row,'link':link,'processor':procs})
    return {'instance':row,'link':link,'processor':procs,'mdb_parameter_count':len(api('/api/mdb/satsentinel_x/parameters').get('parameter',[]))}
def read_stream(case):
    p=BASE/case['case_id']/'yamcs_parameter_stream.csv'; return pd.read_csv(p)
def send_case(df):
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); sent=0
    for ts,g in df.groupby('source_timestamp',sort=True):
        vals=[]
        for r in g.itertuples():
            if pd.isna(r.value): continue
            vals.append({'id':{'name':f'/SATSENTINEL_X/channel_{int(r.channel)}'},'generationTime':iso(ts),'engValue':{'type':'DOUBLE','doubleValue':float(r.value)}})
        if vals:
            sock.sendto(json.dumps({'parameter':vals},separators=(',',':')).encode(),(HOST,PORT)); sent+=1
    sock.close(); return sent
def fetch_history(ch,start,stop):
    name=quote(f'SATSENTINEL_X/channel_{ch}',safe='')
    allvals=[]; pos=0
    for _ in range(200):
        q=f'/api/archive/satsentinel_x/parameters/{name}?start={quote(iso(start))}&stop={quote(iso(stop))}&source=ParameterArchive&noreplay=true&limit=1000&pos={pos}&order=asc'
        try:
            obj=api(q,180); vals=obj.get('parameter',[])
            allvals.extend(vals)
            if len(vals)<1000: return allvals
            pos += len(vals)
        except Exception: pass
        time.sleep(10)
    return allvals
def yamcs_frame(df,channels,start,stop):
    items=[('start',iso(start-timedelta(seconds=CONTEXT))),('stop',iso(stop+timedelta(milliseconds=1))),('namespace','/SATSENTINEL_X'),('delimiter','COMMA'),('header','QUALIFIED_NAME'),('source','ParameterArchive'),('norealtime','true')]
    items += [('parameters',f'SATSENTINEL_X/channel_{ch}') for ch in channels]
    expected={int(ch):int(df[df.channel.eq(ch)].source_timestamp.nunique()) for ch in channels}
    expected_max={int(ch):pd.Timestamp(df[df.channel.eq(ch)].source_timestamp.max()).tz_localize(None) for ch in channels}
    readiness={'case_id':str(df.case_id.iloc[0]),'timeout_seconds':300,'poll_interval_seconds':5,'expected_counts':expected,'expected_final_timestamps':{str(k):str(v) for k,v in expected_max.items()},'polls':0,'ready':False}
    deadline=time.monotonic()+readiness['timeout_seconds']; rows=[]
    while True:
        raw=urlopen(URL+'/api/archive/satsentinel_x:exportParameterValues?'+urlencode(items),timeout=300).read().decode('utf-8','replace')
        rows=[]; reader=csv.DictReader(raw.splitlines())
        for r in reader:
            ts=r.get('Time') or r.get('time')
            for ch in channels:
                k=f'channel_{ch}'
                if r.get(k,'') not in ('',None): rows.append({'source_timestamp':ts,'yamcs_timestamp':ts,'detector_timestamp':ts,'channel':ch,'value':float(r[k]),'parameter':f'esa.channel_{ch}'})
        out=pd.DataFrame(rows,columns=['source_timestamp','yamcs_timestamp','detector_timestamp','channel','value','parameter'])
        if len(out): out=out.drop_duplicates(['channel','yamcs_timestamp'],keep='first')
        observed={int(ch):int(len(out[out.channel.eq(ch)])) for ch in channels}
        observed_max={int(ch):(pd.Timestamp(out[out.channel.eq(ch)].yamcs_timestamp.max()).tz_convert(None) if len(out[out.channel.eq(ch)]) else pd.NaT) for ch in channels}
        readiness['polls']+=1; readiness['observed_counts']=observed; readiness['observed_final_timestamps']={str(k):str(v) for k,v in observed_max.items()}
        if all(observed[ch]==expected[ch] and pd.notna(observed_max[ch]) and observed_max[ch]>=expected_max[ch] for ch in channels):
            readiness['ready']=True; READINESS.append(readiness); return out
        if time.monotonic()>=deadline:
            READINESS.append(readiness); raise RuntimeError('Yamcs archive readiness timeout: '+json.dumps(readiness,default=str))
        time.sleep(readiness['poll_interval_seconds'])
def compare(src,yam,case_id):
    rows=[]
    for ch in sorted(src.channel.unique()):
        a=src[src.channel.eq(ch)].copy(); b=yam[yam.channel.eq(ch)].copy();
        am={pd.Timestamp(x.yamcs_timestamp).tz_convert('UTC').tz_localize(None) if pd.Timestamp(x.yamcs_timestamp).tzinfo else pd.Timestamp(x.yamcs_timestamp):float(x.value) for x in a.itertuples()}
        bm={pd.Timestamp(x.yamcs_timestamp).tz_convert('UTC').tz_localize(None) if pd.Timestamp(x.yamcs_timestamp).tzinfo else pd.Timestamp(x.yamcs_timestamp):float(x.value) for x in b.itertuples()}
        keys=sorted(set(am)|set(bm)); diffs=[]; missing=0
        for k in keys:
            if k not in am or k not in bm: missing+=1
            elif not np.isclose(am[k],bm[k],atol=ATOL,rtol=RTOL,equal_nan=True): diffs.append(abs(am[k]-bm[k]))
        rows.append({'case_id':case_id,'channel':ch,'source_samples':len(am),'yamcs_samples':len(bm),'union_samples':len(keys),'missing_or_extra_samples':missing,'differing_samples':len(diffs),'max_abs_error':max(diffs,default=0.0),'timestamp_exact':set(am)==set(bm),'value_equivalent':not diffs and not missing,'status':'PASS' if not diffs and not missing and set(am)==set(bm) else 'FAIL'})
    return rows
def main():
    OUT.mkdir(parents=True,exist_ok=True); v1=load(V1,'frozen_v1_actual_yamcs'); harness=load(HARNESS,'harness_actual_yamcs'); cases=json.loads(CASES.read_text()); health0=health(); all_events=[]; eqrows=[]; tsrows=[]; streamrows=[]
    for case in cases:
        cid=case['case_id']; src=read_stream(case); start=pd.Timestamp(case['start_time']); stop=pd.Timestamp(case['end_time']);
        sent=send_case(src); time.sleep(2); yam=yamcs_frame(src,case['channel_list'],start,stop)
        yam.to_csv(OUT/f'{cid}_yamcs_retrieved.csv',index=False); eqrows += compare(src,yam,cid)
        tsrows.append({'case_id':cid,'source_start':case['start_time'],'source_end':case['end_time'],'yamcs_min':yam.yamcs_timestamp.min() if len(yam) else '','yamcs_max':yam.yamcs_timestamp.max() if len(yam) else '','timestamp_exact':bool(len(yam) and pd.Timestamp(yam.yamcs_timestamp.min()).tz_convert(None)>=start-timedelta(seconds=CONTEXT)),'udp_datagrams_sent':sent,'retrieved_rows':len(yam)})
        chrows=[]
        for ch in case['channel_list']:
            g=yam[yam.channel.eq(ch)].copy(); idx=pd.DatetimeIndex(pd.to_datetime(g.yamcs_timestamp,utc=True)).tz_localize(None); s=pd.Series(g.value.to_numpy(float),index=idx).sort_index(); f=v1.describe_channel(s,start,stop); chrows.append({'case_id':cid,'channel':ch,'parameter':f'esa.channel_{ch}',**f})
        pd.DataFrame(chrows).to_csv(OUT/f'{cid}_detector_channel_evidence.csv',index=False)
        agg=harness.aggregate(case,chrows,v1); ev={'case_id':cid,'source_id':case['source_event_id'],'event_score':agg['detector_score'],'classification':agg['detector_classification'],'detector_hash':sha(V1),'retrieval_status':'PASS' if len(yam) else 'FAIL','udp_datagrams_sent':sent,**{k:v for k,v in agg.items() if k not in ('detector_score','detector_classification')}}; all_events.append(ev); pd.DataFrame([ev]).to_csv(OUT/f'{cid}_detector_event_evidence.csv',index=False)
    pd.DataFrame(all_events).to_csv(OUT/'yamcs_replay_results.csv',index=False); pd.DataFrame(eqrows).to_csv(OUT/'yamcs_channel_equivalence.csv',index=False); pd.DataFrame(tsrows).to_csv(OUT/'timestamp_equivalence.csv',index=False)
    refs=pd.read_csv(YAMCS/'yamcs_detector_input_equivalence.csv'); results=[]
    for e in all_events:
        r=refs[refs.case_id.eq(e['case_id'])].iloc[0]; results.append({'case_id':e['case_id'],'reference_score':float(r.replay_score),'actual_yamcs_score':float(e['event_score']),'score_delta':float(e['event_score'])-float(r.replay_score),'classification_match':str(r.classification_match).lower()=='true' or str(r.classification_match)=='True','status':'PASS' if abs(float(e['event_score'])-float(r.replay_score))<ATOL else 'FAIL'})
    report={'status':'PASS' if all(x['status']=='PASS' for x in eqrows+results) else 'FAIL','health':health0,'detector_hash':sha(V1),'six_cases':[x['case_id'] for x in cases],'tolerance':{'atol':ATOL,'rtol':RTOL},'source_streams':'pre-existing yamcs/outputs/case_*/yamcs_parameter_stream.csv','archive_readiness':READINESS,'notes':'Actual UDP -> Yamcs parameter history -> frozen Detector v1; no six-case detector replay artifact was modified.'}
    (OUT/'input_equivalence_report.json').write_text(json.dumps({'status':report['status'],'channels':eqrows,'timestamps':tsrows,'archive_readiness':READINESS},indent=2,default=str)); (OUT/'score_equivalence_report.json').write_text(json.dumps(results,indent=2)); (OUT/'actual_yamcs_equivalence_report.json').write_text(json.dumps(report,indent=2,default=str)); (OUT/'integrity_report.json').write_text(json.dumps({'status':report['status'],'detector_hash':sha(V1),'container':'satsentinel-yamcs-esa','endpoint':URL,'mapping_file':str(HERE/'yamcs_parameter_mapping.json')},indent=2)); (HERE/'actual_yamcs_equivalence_interpretation.md').write_text('# Actual Yamcs six-case equivalence\n\nThe report records a real UDP Parameter Data Link replay into the running `satsentinel_x` instance, retrieval from Yamcs parameter history, and evaluation by the immutable Detector v1. Controls remain label-negative/unlabelled and are not proven nominal. Archive readiness was accepted only after every requested channel reached its source row count and final timestamp.\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'cases':len(all_events),'channels':len(eqrows),'detector_hash':sha(V1)},indent=2))
if __name__=='__main__': main()
