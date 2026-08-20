"""One-value real ESA -> actual Yamcs UDP -> parameter API smoke test."""
from pathlib import Path
import json, socket, time, urllib.request
import pandas as pd

ROOT=Path(r"E:\SATSentinel-RealTelemetry"); INS=ROOT/'inspection'; OUT=ROOT/'yamcs/actual_server'
BASE_URL='http://localhost:8091'; INSTANCE='satsentinel_x'; PROCESSOR='realtime'; CHANNEL=41; PARAM='/SATSENTINEL_X/channel_41'; UDP=('127.0.0.1',11016)

def get(path):
 with urllib.request.urlopen(BASE_URL+path,timeout=10) as r: return json.loads(r.read().decode())

def main():
 p=INS/'selected_channels/channel_41/channel_41'; d=pd.read_pickle(p); s=d.iloc[:,0].astype(float); idx=pd.DatetimeIndex(s.index); idx=idx.tz_convert('UTC').tz_localize(None) if idx.tz else idx; s.index=idx
 source_ts=pd.Timestamp('2007-05-22T05:30:06.120'); value=float(s.loc[source_ts])
 wire_ts=source_ts.tz_localize('UTC').isoformat().replace('+00:00','Z')
 before=get('/api/links/satsentinel_x')['links'][0]['dataInCount']
 payload={'parameter':[{'id':{'name':PARAM},'generationTime':wire_ts,'engValue':{'type':'DOUBLE','doubleValue':value}}]}
 with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock: sock.sendto(json.dumps(payload,separators=(',',':')).encode(),UDP)
 response=None; last=None
 for _ in range(30):
  time.sleep(.25)
  last=get(f'/api/processors/{INSTANCE}/{PROCESSOR}/parameters/SATSENTINEL_X/channel_41')
  if last.get('engValue') and last.get('generationTime'): response=last; break
 after=get('/api/links/satsentinel_x')['links'][0]['dataInCount']
 result={'status':'PASS' if response and float(response['engValue'].get('doubleValue',response['engValue'].get('floatValue'))) == value and pd.Timestamp(response['generationTime']).tz_convert('UTC').tz_localize(None)==source_ts else 'FAIL','container_endpoint':BASE_URL,'instance':INSTANCE,'processor':PROCESSOR,'parameter':PARAM,'source_file':str(p),'source_timestamp_utc_naive':source_ts.isoformat(),'wire_generation_time':wire_ts,'source_value':value,'yamcs_response':response or last,'yamcs_value':float(response['engValue'].get('doubleValue',response['engValue'].get('floatValue'))) if response and response.get('engValue') else None,'yamcs_generation_time':response.get('generationTime') if response else None,'link_datagrams_before':before,'link_datagrams_after':after,'mapping':'channel_41 -> /SATSENTINEL_X/channel_41 -> detector channel 41','conversion':'identity','missing_value_handling':'not applicable; selected source value finite'}
 (OUT/'smoke_test_result.json').write_text(json.dumps(result,indent=2,default=str),encoding='utf-8'); print(json.dumps(result,indent=2,default=str))
if __name__=='__main__': main()
