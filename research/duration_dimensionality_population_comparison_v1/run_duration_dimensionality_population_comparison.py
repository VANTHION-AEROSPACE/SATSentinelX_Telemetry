from pathlib import Path
import hashlib, json, math, platform
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(r'E:\SATSentinel-RealTelemetry'); OUT=ROOT/'research/duration_dimensionality_population_comparison_v1'
EVAL=ROOT/'inspection/class3_detector_v1_broader_evaluation_v1/broader_v1_evaluation.csv'
FEATURES=ROOT/'inspection/esa_broader_control_characterization_v1/feature_table.csv'
CONTROLS=ROOT/'inspection/esa_broader_control_characterization_v1/control_sampling_frame.csv'
STRUCTURED=['population_comparison.csv','duration_summary.csv','channel_count_summary.csv','duration_stratification.csv','channel_count_stratification.csv','effect_sizes.csv','distribution_comparison.csv','population_comparison_report.json','population_comparison_interpretation.md']
PROTECTED=[ROOT/'inspection/class3_detector_v1.py',ROOT/'inspection/class3_detector_v2/class3_detector_v2.py',ROOT/'inspection/class3_detector_results.csv',ROOT/'inspection/class3_detector_evaluation.csv',EVAL,ROOT/'inspection/class3_detector_v1_broader_evaluation_v1/broader_v1_event_results.csv',FEATURES,CONTROLS,ROOT/'inspection/mission1/labels.csv',ROOT/'inspection/mission1/anomaly_types.csv',ROOT/'inspection/mission1/channels.csv',ROOT/'external/opssat-ad/data/raw/dataset.csv',ROOT/'external/opssat-ad/data/raw/segments.csv',ROOT/'yamcs/actual_server/smoke_test_result.json',ROOT/'yamcs/actual_server/six_case_equivalence/outputs/score_equivalence_report.json',ROOT/'yamcs/actual_server/six_case_equivalence/readiness_failure_forensic_report.md',ROOT/'research/final_evidence_audit_v2/canonical_results.csv',ROOT/'research/final_evidence_audit_v2/claim_evidence_matrix.csv',ROOT/'research/final_evidence_audit_v2/experiment_registry.csv',ROOT/'research/final_evidence_audit_v2/failure_mode_taxonomy.csv',ROOT/'research/final_evidence_audit_v2/reviewer_attack_surface.csv',ROOT/'research/final_evidence_audit_v2/paper_story_v1.md']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def clean(x):
 if isinstance(x,(np.integer,np.floating)): x=x.item()
 return None if isinstance(x,float) and (math.isnan(x) or math.isinf(x)) else x
def rec(df): return [{k:clean(v) for k,v in r.items()} for r in df.to_dict('records')]
def summary(a):
 a=np.asarray(a,dtype=float); q=np.quantile(a,[.01,.05,.10,.25,.50,.75,.90,.95,.99])
 return {'n':len(a),'minimum':float(a.min()),'maximum':float(a.max()),'median':float(np.median(a)),'mean':float(a.mean()),'standard_deviation':float(np.std(a,ddof=1)),'q01':float(q[0]),'q05':float(q[1]),'q10':float(q[2]),'q25':float(q[3]),'q50':float(q[4]),'q75':float(q[5]),'q90':float(q[6]),'q95':float(q[7]),'q99':float(q[8]),'iqr':float(q[5]-q[3])}
def overlap(a,b):
 lo=min(a.min(),b.min()); hi=max(a.max(),b.max())
 if lo==hi:return 1.0
 bins=np.linspace(lo,hi,101); ha,_=np.histogram(a,bins,density=True); hb,_=np.histogram(b,bins,density=True)
 return float(np.sum(np.minimum(ha,hb)*np.diff(bins)))
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 prior={n:sha(OUT/n) for n in STRUCTURED if (OUT/n).exists() and n!='population_comparison_interpretation.md'}
 before={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in PROTECTED if p.exists()}
 e=pd.read_csv(EVAL); f=pd.read_csv(FEATURES); c=pd.read_csv(CONTROLS)
 pos=f[f.event_id.isin(e.loc[e.label.eq('POSITIVE'),'event_id'])].copy(); con=c.copy()
 if len(pos)!=30 or len(con)!=170: raise RuntimeError(f'fixed population mismatch: {len(pos)}, {len(con)}')
 pos['population']='CLASS3_POSITIVE'; con['population']='LABEL_NEGATIVE_UNLABELLED_CONTROL'
 cols=['event_id','population','duration_seconds','channel_count','duration_bucket','channel_bucket']
 x=pd.concat([pos[cols],con[cols]],ignore_index=True)
 rows=[]
 for pop,g in x.groupby('population',sort=False):
  for var in ['duration_seconds','channel_count']:
   z=summary(g[var]); z.update({'population':pop,'variable':var}); rows.append(z)
 pd.DataFrame(rows).to_csv(OUT/'population_comparison.csv',index=False,float_format='%.15g')
 pd.DataFrame([{**summary(g.duration_seconds),'population':pop} for pop,g in x.groupby('population',sort=False)]).to_csv(OUT/'duration_summary.csv',index=False,float_format='%.15g')
 pd.DataFrame([{**summary(g.channel_count),'population':pop} for pop,g in x.groupby('population',sort=False)]).to_csv(OUT/'channel_count_summary.csv',index=False,float_format='%.15g')
 def strata(col,order):
  z=[]
  for s in order:
   for pop,g in x.groupby('population',sort=False):
    n=int((g[col].astype(str)==s).sum()); z.append({'population':pop,'stratum':s,'n':n,'proportion_within_population':n/len(g),'existing_bin_definition':True})
  return pd.DataFrame(z)
 ds=strata('duration_bucket',['IMPULSIVE','SHORT','MEDIUM','LONG','PERSISTENT']); cs=strata('channel_bucket',['1-6','7-12','13-26'])
 ds.to_csv(OUT/'duration_stratification.csv',index=False,float_format='%.15g'); cs.to_csv(OUT/'channel_count_stratification.csv',index=False,float_format='%.15g')
 a=pos; b=con; effects=[]; comps=[]
 for var in ['duration_seconds','channel_count']:
  av=a[var].to_numpy(float); bv=b[var].to_numpy(float); pooled=np.sqrt(((len(av)-1)*np.var(av,ddof=1)+(len(bv)-1)*np.var(bv,ddof=1))/(len(av)+len(bv)-2)); d=(av.mean()-bv.mean())/pooled if pooled else 0; g=d*(1-3/(4*(len(av)+len(bv))-9)); u=stats.mannwhitneyu(av,bv,alternative='two-sided'); rb=2*u.statistic/(len(av)*len(bv))-1; ks=stats.ks_2samp(av,bv)
  effects.append({'variable':var,'positive_n':len(av),'control_n':len(bv),'cohens_d_positive_minus_control':d,'hedges_g_positive_minus_control':g,'rank_biserial_positive_vs_control':rb,'interpretation':'standardized descriptive contrast; not causal'})
  comps.append({'variable':var,'positive_n':len(av),'control_n':len(bv),'mann_whitney_u':float(u.statistic),'mann_whitney_p_value':float(u.pvalue),'ks_statistic':float(ks.statistic),'ks_p_value':float(ks.pvalue),'histogram_overlap_coefficient_100_bins':overlap(av,bv),'interpretation':'non-parametric descriptive comparison; not causal'})
 pd.DataFrame(effects).to_csv(OUT/'effect_sizes.csv',index=False,float_format='%.15g'); pd.DataFrame(comps).to_csv(OUT/'distribution_comparison.csv',index=False,float_format='%.15g')
 ed={r['variable']:r for r in effects}; cc={r['variable']:r for r in comps}; maxg=max(abs(ed['duration_seconds']['hedges_g_positive_minus_control']),abs(ed['channel_count']['hedges_g_positive_minus_control'])); cls='C_STRONGLY_SHIFTED' if maxg>=.8 else ('B_MODERATELY_SHIFTED' if maxg>=.5 else 'A_BROADLY_SIMILAR'); status='HIGH' if cls.startswith('C') else ('MODERATE' if cls.startswith('B') else 'LOW')
 before_after={'before':before,'after':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in PROTECTED if p.exists()}}; before_after['unchanged']=before==before_after['after']
 report={'analysis_version':'duration_dimensionality_population_comparison_v1','population_definition':{'class3_positive_n':30,'control_n':170,'control_label':'LABEL_NEGATIVE_UNLABELLED','population_frozen':True,'detector_outputs_used_to_define_comparison':False},'summaries':{'duration':rec(pd.read_csv(OUT/'duration_summary.csv')),'channel_count':rec(pd.read_csv(OUT/'channel_count_summary.csv'))},'stratification':{'duration':rec(ds),'channel_count':rec(cs)},'effect_sizes':effects,'distribution_comparison':comps,'classification':cls,'structural_confound_status':status,'interpretation_limits':['Descriptive comparison does not establish causality.','30/30 remains a stated-population result, not general accuracy.','40/170 remains unchanged and controls are not proven nominal.'],'integrity':before_after}
 (OUT/'population_comparison_report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 text=f'''# Duration–Dimensionality Population Comparison v1\n\nThis analysis compares the frozen 30 established Class-3 positives with the frozen 170 predetermined `LABEL_NEGATIVE_UNLABELLED` controls. Detector outputs did not define, select, or remove observations.\n\n## Result\n\nClassification: **{cls}**. Structural-confound status: **{status}**. The standardized descriptive contrasts, non-parametric comparisons, overlaps, and existing-bin counts are in the CSV outputs.\n\n1. **Duration:** positives are {'structurally different' if abs(ed['duration_seconds']['hedges_g_positive_minus_control'])>=.5 else 'not strongly shifted'} from controls by the descriptive standardized contrast.\n2. **Channel dimensionality:** positives are {'structurally different' if abs(ed['channel_count']['hedges_g_positive_minus_control'])>=.5 else 'not strongly shifted'} from controls by the descriptive standardized contrast.\n3. **Detector concern:** this {'strengthens' if cls!='A_BROADLY_SIMILAR' else 'weakens'} concern that detector behavior may partly reflect structural properties, while preserving the prior score/channel-count association.\n4. **30/30:** remains valid only for the stated evaluated Class-3 population and does not support broad generalization.\n5. **23.53%:** the canonical 40/170 = 23.5294% control-detection rate is unchanged; this comparison does not make it a nominal FPR.\n6. **Detector modification:** NO. This is characterization only and does not justify changing Detector v1.\n\nDuration and dimensionality differences do not prove that either property causes detections.\n\n## STRUCTURAL-CONFOUND STATUS: {status}\n\nThis status reflects observed population shifts, not detector performance or a causal conclusion.\n'''
 (OUT/'population_comparison_interpretation.md').write_text(text,encoding='utf-8')
 current={n:sha(OUT/n) for n in STRUCTURED if (OUT/n).exists()}; repro='PASS' if prior and all(prior.get(k)==v for k,v in current.items() if k in prior) else 'NOT_YET_COMPARED'
 (OUT/'population_comparison_reproducibility.json').write_text(json.dumps({'analysis_version':'duration_dimensionality_population_comparison_v1','reproducibility_status':repro,'compared_previous_output_hashes':bool(prior),'output_sha256':current,'protected_integrity':before_after['unchanged']},indent=2,sort_keys=True)+'\n',encoding='utf-8')
 manifest={'analysis_version':'duration_dimensionality_population_comparison_v1','inputs':{'broader_evaluation':str(EVAL.relative_to(ROOT)),'feature_table':str(FEATURES.relative_to(ROOT)),'control_sampling_frame':str(CONTROLS.relative_to(ROOT))},'fixed_population':{'class3_positive_n':30,'control_n':170},'source_sha256_before':before,'source_sha256_after':before_after['after'],'source_integrity_unchanged':before_after['unchanged'],'generated_files':sorted(p.name for p in OUT.iterdir() if p.is_file()),'no_detector_or_population_change':True}
 (OUT/'population_comparison_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps({'classification':cls,'structural_confound_status':status,'reproducibility':repro,'integrity':before_after['unchanged']},indent=2))
 if not before_after['unchanged']: raise RuntimeError('protected artifact hash changed')
if __name__=='__main__': main()
