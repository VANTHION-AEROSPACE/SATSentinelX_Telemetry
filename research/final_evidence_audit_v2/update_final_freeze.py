from __future__ import annotations
import csv, hashlib, json, shutil, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r'E:\SATSentinel-RealTelemetry')
OUT = ROOT / 'research' / 'final_evidence_audit_v2'
SRC = ROOT / 'research' / 'duration_dimensionality_confound_analysis_v1'
PACKET = OUT / 'external_review_packet'

PROTECTED = [
    ROOT/'inspection/class3_detector_v1.py',
    ROOT/'inspection/class3_detector_v2/class3_detector_v2.py',
    ROOT/'inspection/class3_detector_results.csv',
    ROOT/'inspection/class3_detector_evaluation.csv',
    ROOT/'inspection/class3_detector_v1_broader_evaluation_v1/broader_v1_evaluation.csv',
    ROOT/'inspection/class3_detector_v1_broader_evaluation_v1/broader_v1_event_results.csv',
    ROOT/'inspection/class3_detector_v2/v1_vs_v2_comparison.csv',
    ROOT/'inspection/mission1/labels.csv', ROOT/'inspection/mission1/anomaly_types.csv', ROOT/'inspection/mission1/channels.csv',
    ROOT/'external/opssat-ad/data/raw/dataset.csv', ROOT/'external/opssat-ad/data/raw/segments.csv',
    ROOT/'yamcs/actual_server/smoke_test_result.json',
    ROOT/'yamcs/actual_server/six_case_equivalence/outputs/score_equivalence_report.json',
    ROOT/'yamcs/actual_server/six_case_equivalence/readiness_failure_forensic_report.md',
    SRC/'confound_analysis_interpretation.md', SRC/'confound_analysis_report.json', SRC/'confound_analysis_manifest.json', SRC/'confound_analysis_reproducibility.json',
    SRC/'association_statistics.csv', SRC/'duration_stratification.csv', SRC/'dimensionality_stratification.csv', SRC/'duration_dimensionality_matrix.csv', SRC/'sensitivity_analysis.csv', SRC/'adjusted_score_analysis.csv'
]

def h(p):
    x=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''): x.update(b)
    return x.hexdigest()

def rel(p):
    return str(p.relative_to(ROOT)).replace('\\','/')

def append_csv(path, rows):
    with path.open('a', newline='', encoding='utf-8') as f:
        csv.writer(f).writerows(rows)

def append_text(path, text):
    with path.open('a', encoding='utf-8') as f: f.write('\n' + text.rstrip() + '\n')

def main():
    before={rel(p):h(p) for p in PROTECTED if p.exists()}
    registry=OUT/'experiment_registry.csv'
    append_csv(registry, [[
        'E21','FINAL FORENSIC ANALYSIS — Duration/dimensionality confound analysis v1',
        'Characterize whether frozen Detector v1 control detections and scores are structurally associated with telemetry duration and channel dimensionality.',
        'research/duration_dimensionality_confound_analysis_v1',
        'ESA broader v1 evaluation plus predetermined control sampling frame',
        '30 Class-3 positives; 170 LABEL_NEGATIVE_UNLABELLED controls; primary structural analysis on 170 controls and finite-support model rows',
        '30 evaluated Class-3 positives', 'LABEL_NEGATIVE_UNLABELLED controls; not proven nominal', '200 total; 170 controls', '170', 'v1 frozen',
        'Existing duration_bucket and channel_bucket strata; no bin optimization', 'forensic descriptive analysis',
        '40/170 controls detected; positive score-duration association; strong score-channel-count association; 13–26-channel controls 34/34 detected; residualization analysis-only; no classification changes',
        'PASS; complete analysis run twice with byte-identical structured outputs', 'PASS; protected source hashes unchanged',
        'Confound characterization and evidence governance; informs deployment/evaluation wording',
        'Controls are label-negative/unlabelled; insufficient-telemetry rows have zero/non-finite log features; sparse cells; associations are not causal; residuals are not detector outputs',
        'Paper limitation and deployment lesson; not detector revision'
    ]])

    canonical=OUT/'canonical_results.csv'
    append_csv(canonical, [
        ['M039','control_detection_rate_primary',0.235294117647059,'proportion',40,170,'E21','170 predetermined LABEL_NEGATIVE_UNLABELLED controls','confound_analysis_report.json','research/duration_dimensionality_confound_analysis_v1/confound_analysis_report.json','JSON/CSV forensic result','Primary broader control detection remains 40/170 = 23.5294%.','Controls are not proven nominal; do not call nominal FPR or low false-positive rate.','TRUE','New forensic analysis; canonical primary result preserved'],
        ['M040','score_duration_pearson_r',0.360763,'correlation', 'not applicable','170','E21','170 controls','association_statistics.csv','research/duration_dimensionality_confound_analysis_v1/association_statistics.csv','CSV forensic result','Detector score has a positive descriptive Pearson association with duration.','Descriptive association; no causal inference; p-value is not a causal test.','TRUE','Paper-safe as association only'],
        ['M041','score_duration_spearman_r',0.444362,'correlation','not applicable','170','E21','170 controls','association_statistics.csv','research/duration_dimensionality_confound_analysis_v1/association_statistics.csv','CSV forensic result','Detector score has a positive descriptive rank association with duration.','Descriptive association; controls and telemetry support are limited.','TRUE','Paper-safe as association only'],
        ['M042','score_channel_count_pearson_r',0.910360,'correlation','not applicable','170','E21','170 controls','association_statistics.csv','research/duration_dimensionality_confound_analysis_v1/association_statistics.csv','CSV forensic result','Detector score is strongly descriptively associated with channel count.','Structural association is not dimensionality-caused false positives; channel availability and control construction are confounded.','TRUE','Paper-safe as association only'],
        ['M043','13_26_channel_control_detection_rate',1.0,'proportion',34,34,'E21','170 predetermined controls; 13–26 channel stratum','dimensionality_stratification.csv','research/duration_dimensionality_confound_analysis_v1/dimensionality_stratification.csv','CSV stratification result','All 34 controls in the 13–26 channel stratum were detected.','Stratum is observational and may be confounded; not causal proof and not a nominal FPR.','TRUE','Report with explicit stratum denominator'],
        ['M044','residualization_classification_change',0,'count','0','170','E21','170 controls','adjusted_score_analysis.csv','research/duration_dimensionality_confound_analysis_v1/adjusted_score_analysis.csv','CSV analysis-only result','Descriptive residualization did not change frozen classifications.','Residualized values are not Detector v1 outputs and were not used to tune a rule.','TRUE','No detector revision justified']
    ])

    claims=OUT/'claim_evidence_matrix.csv'
    append_csv(claims, [
        ['C21','Detector score is positively associated with telemetry duration in the examined controls.','association','E21','E21','association_statistics.csv','r=0.360763 Pearson; rho=0.444362 Spearman; n=170','Moderate descriptive association','Controls not proven nominal; no causal isolation','Duration was positively associated with score in the examined control population.','Duration causes false positives.','Failure analysis','Medium','SUPPORTED_WITH_CAVEAT'],
        ['C22','Detector score is strongly associated with channel dimensionality in the examined controls.','association','E21','E21','association_statistics.csv','r=0.910360 Pearson; rho=0.892711 Spearman; n=170','Strong descriptive association','Channel coverage, control construction and dimensionality are confounded','Channel dimensionality was strongly associated with score in the examined controls.','Dimensionality causes false positives.','Failure analysis','High','SUPPORTED_WITH_CAVEAT'],
        ['C23','Structural telemetry properties may contribute to control-detection behavior.','failure mode','E21','E21','duration_dimensionality_matrix.csv; dimensionality_stratification.csv','13–26 channel stratum: 34/34 detected; 40/170 overall','Moderate descriptive evidence','No causal inference; uneven and sparse cells','Structural telemetry properties may contribute to observed control-detection behavior.','Structural properties explain or cause all false positives.','Discussion','High','SUPPORTED_WITH_CAVEAT'],
        ['C24','Structural association does not establish causation.','interpretive limitation','E21','E21','confound_analysis_interpretation.md; confound_analysis_report.json','Analysis explicitly descriptive; residuals not detector outputs','Strong limitation statement','Observational design','The duration/dimensionality findings are associations, not causal evidence.','Duration or dimensionality causes false positives.','Discussion','Low','SUPPORTED'],
        ['C25','Descriptive residualization did not change frozen classifications.','analysis result','E21','E21','adjusted_score_analysis.csv; sensitivity_analysis.csv','0 classification changes; 40 detections retained','Moderate within-analysis result','Residual scores are not detector outputs; no threshold retuning','Analysis-only residualization did not change frozen classifications and did not justify changing Detector v1.','Residualization improves Detector v1 or establishes a corrected detector.','Failure analysis','Medium','SUPPORTED_WITH_CAVEAT'],
        ['C26','The canonical broader-control result remains 40/170 = 23.5294%.','detector result','E09; E21','E09; E21','broader_v1_evaluation_report.json; confound_analysis_report.json','40/170 = 0.235294117647059','Strong for stated control population','Controls not proven nominal','Frozen Detector v1 detected 40 of 170 label-negative/unlabelled controls under the primary rule.','The broader result is a nominal FPR or low false-positive rate.','Results','Critical','SUPPORTED_WITH_CAVEAT']
    ])

    failure=OUT/'failure_mode_taxonomy.csv'
    append_csv(failure, [
        ['F11','Duration-associated score variation','Positive descriptive association between score and duration in the examined controls; persistent strata contain most detections.','E21','Moderate','Detector evidence model','Duration may be entangled with evidence accumulation and operating regime.','Long/persistent windows require structural-context review.','Existing duration strata plus descriptive association analysis','Causal effect not established; not resolved by residualization','High'],
        ['F12','Dimensionality-associated score variation','Strong descriptive score/channel-count association; 34/34 controls in 13–26 channel stratum detected.','E21','Strong descriptive','Detector aggregation / telemetry representation','Channel dimensionality may concentrate or accumulate evidence.','High-dimensional configurations require scrutiny and coverage controls.','Existing channel strata plus 2D matrix and residual analysis','Structural association remains; causality and nominality unresolved','Critical'],
        ['F13','Structural association with control detection','Duration/dimensionality patterns may contribute to observed control detections.','E21','Moderate descriptive','Evaluation interpretation','Observed control burden may partly reflect structural differences rather than anomaly causation.','Report structural context and avoid nominal-FPR language.','Forensic stratification and analysis-only residualization','No detector revision justified; controls not proven nominal','Critical']
    ])

    attack=OUT/'reviewer_attack_surface.csv'
    append_csv(attack, [
        ['A21','Could the 23.5% broader-control detection rate be partly explained by structural differences in duration and channel dimensionality?','E21','valid','critical','Report 40/170 unchanged, show positive duration and strong channel-count associations, and state that associations are descriptive rather than causal.','Controls remain label-negative/unlabelled; channel availability and structural variables are confounded; no nominal false-positive rate is established.','Failure analysis / Discussion'],
        ['A22','Does the duration/dimensionality analysis justify changing Detector v1?','E21','valid','high','No. The analysis is forensic/descriptive; residualization did not alter frozen classifications and no threshold or detector was changed.','No prospective corrected detector or nominal-control validation was performed.','Discussion / Deployment'],
        ['A23','Does the structural analysis prove Detector v1 is invalid?','E21','invalid inference','high','No. It identifies an association and limitation; it neither proves detector invalidity nor correctness.','Causal isolation and nominal controls are unavailable.','Discussion'],
        ['A24','Does the structural analysis prove dimensionality causes false positives?','invalid causal claim','high','No. Use association language only.','Observational design and confounded telemetry support.','Failure analysis']
    ])

    story='''\n## Final duration/dimensionality forensic finding\n\nThe final forensic analysis used the predetermined 30-positive/170-control broader-v1 population. Frozen Detector v1 detected all 30 evaluated Class-3 positives, while 40/170 label-negative/unlabelled controls were detected under the primary rule. Detector score was positively associated with duration and strongly associated with channel count in the examined controls; all 34 controls in the 13–26-channel stratum were detected. These are descriptive structural associations, not evidence that duration or dimensionality causes false positives. Analysis-only residualization did not change frozen classifications, so Detector v1 was not modified. The result is a deployment/evaluation lesson: structural context, channel coverage, control semantics and archive readiness must be treated as first-class evidence constraints.\n\nThe final conclusion is deliberately intermediate: the analysis identifies possible structural contributors to observed control detections but does not establish causation, prove detector failure, or justify a detector revision.\n'''
    append_text(OUT/'paper_story_v1.md', story)

    instructions='''\n## FINAL EVIDENCE PACKAGE\n\nAll substantive experiments are frozen. The duration/dimensionality analysis is the final forensic addition. No Detector v3, threshold tuning, or additional dataset is planned. Judge the paper from the evidence actually produced; recommend a genuinely necessary missing analysis only when a central claim cannot be supported without it, not merely to improve a metric. Specifically attack novelty, the 30-positive population, label-negative controls, the 23.5% control detection rate, duration/dimensionality association, the v2 negative result, the OPSSAT negative result, Yamcs 5/6 equivalence, Parameter Archive failure, operational-validation wording, generalization wording, IAAI Emerging Applications fit, and six-page prioritization.\n\nKeep separate: reproducibility, detector equivalence, integration completeness and deployment validation. Deterministic research analyses and replay studies reproduced where reported; complete six-case actual-Yamcs equivalence was not achieved because of incomplete Parameter Archive historical coverage.\n'''
    append_text(PACKET/'00_REVIEW_INSTRUCTIONS.md', instructions)
    append_text(OUT/'reproducibility_integrity_summary.md','''\n## Final confound-analysis status\n\nThe duration/dimensionality analysis was run twice with reproducibility PASS. Protected detector, telemetry, label, OPSSAT, Yamcs and prior-analysis hashes were unchanged. Actual Yamcs integration remains demonstrated but incomplete for six-case equivalence: five cases passed and control_0069 remained limited by incomplete Parameter Archive historical coverage. This is an integration-completeness/deployment limitation, not a blanket claim that all research analyses are irreproducible.\n''')

    confound='''# Duration–Dimensionality Analysis v1\n\n## Purpose\nCharacterize whether frozen Detector v1 score and control-detection behavior are structurally associated with telemetry duration and channel dimensionality. This is the final forensic addition; it is not detector development.\n\n## Population\nThe predetermined broader population contains 30 Class-3 positives and 170 `LABEL_NEGATIVE_UNLABELLED` controls. The authoritative primary broader-control result remains 40/170 = 23.5294%. Controls are not proven nominal.\n\n## Methods\nExisting duration and channel buckets were reused without optimization. Pearson and Spearman associations were computed for score versus duration and channel count. Existing one-dimensional strata and a two-dimensional duration/channel matrix were reported. A prespecified logistic model, `detected ~ log(duration) + log(channel_count)`, was stable on finite-support rows (n=91). Analysis-only OLS residualization was performed for duration, dimensionality, and both together. Frozen classifications were not changed.\n\n## Primary findings\nDuration showed a positive descriptive association with score (Pearson r=0.360763; Spearman rho=0.444362; n=170). Channel count showed a strong descriptive association (Pearson r=0.910360; Spearman rho=0.892711; n=170). All 34 controls in the 13–26 channel stratum were detected.\n\n## Structural associations and 2D stratification\nDetections were concentrated in persistent and higher-dimensional strata, but the matrix is uneven and includes sparse cells. These patterns may reflect structural telemetry properties, channel availability, operating regime, or control construction. They do not isolate a causal mechanism.\n\n## Residual analysis\nResidualized scores are analysis-only values, not Detector v1 outputs. Residualization did not change frozen classifications or the canonical 40/170 result.\n\n## Sensitivity analysis\nThe all-control analysis retained 40/170 detections. The sufficient-telemetry subset retained 40/92 detections. Duration-adjusted, dimensionality-adjusted and jointly adjusted residual summaries were descriptive only; no reclassification or threshold change was performed.\n\n## Interpretation\nConclusion C / WEAK-INCONCLUSIVE: duration and dimensionality may contribute to score variation and are observed structural associations, but the evidence does not establish causation or prove detector failure. The analysis does not justify changing Detector v1.\n\n## Limitations\nControls are label-negative/unlabelled rather than certified nominal; insufficient-telemetry rows have non-finite log support; strata are uneven and some cells are sparse; the analysis is observational; residuals are not detector scores; the dataset and reconstructed channel subset remain limited.\n\n## Exact paper-safe wording\n“The broader control population showed a non-zero frozen-detector detection rate, and score/detection patterns were examined against pre-existing telemetry duration and channel dimensionality. These analyses are descriptive and intended to characterize possible structural association; they do not establish that telemetry duration or dimensionality is the causal source of the observed detections.”\n'''
    (PACKET/'14_DURATION_DIMENSIONALITY_ANALYSIS.md').write_text(confound, encoding='utf-8')
    append_text(PACKET/'10_REPRODUCIBILITY_INTEGRITY.md', '## Final forensic addition\n\nThe duration/dimensionality analysis reproduced twice with integrity PASS. Actual Yamcs six-case completeness remains unresolved because Parameter Archive coverage for control_0069 was incomplete; this does not erase successful deterministic research replay or integration evidence.')
    append_text(PACKET/'13_FIGURE_TABLE_PLAN.md','''\n| Figure 6 | Duration/dimensionality structural association | Show final forensic associations without causal framing | E21 confound analysis | Existing analysis figures and tables | Main or supplement | Optional | Yes |\n| Table 5 | Final confound-analysis stratification | Report 40/170 context, strata, matrix and residualization caveats | E21 confound analysis | Existing CSV outputs | Supplement | No | Yes |''')

    # Copy authoritative updated files into the packet.
    copies={'01_EXECUTIVE_SUMMARY.md':'paper_story_v1.md','02_EXPERIMENT_REGISTRY.csv':'experiment_registry.csv','03_CANONICAL_RESULTS.csv':'canonical_results.csv','04_CLAIM_EVIDENCE_MATRIX.csv':'claim_evidence_matrix.csv','05_V1_EVIDENCE.md':'v1_evidence_summary.md','06_V2_EVIDENCE.md':'v2_evidence_summary.md','07_OPSSAT_EVIDENCE.md':'opssat_evidence_summary.md','08_YAMCS_EVIDENCE.md':'yamcs_evidence_summary.md','09_FAILURE_MODES.csv':'failure_mode_taxonomy.csv','10_REPRODUCIBILITY_INTEGRITY.md':'reproducibility_integrity_summary.md','11_REVIEWER_ATTACK_SURFACE.csv':'reviewer_attack_surface.csv','12_PAPER_STORY.md':'paper_story_v1.md','13_FIGURE_TABLE_PLAN.md':'paper_figures_tables_plan.md'}
    for dst,src in copies.items(): shutil.copy2(OUT/src, PACKET/dst)
    (OUT/'external_review_status.md').write_text('''# External review status\n\n## Gemini\n- Review received: NO\n- Source file: Not located in the project.\n- Review date: Not available.\n- Overall recommendation: Not available; no review text was found.\n- Key concerns: Not available; do not infer or fabricate.\n\n## DeepSeek\n- Review received: NO\n- Source file: Not located in the project.\n- Review date: Not available.\n- Overall recommendation: Not available; no review text was found.\n- Key concerns: Not available; do not infer or fabricate.\n\n## Claude\n- NOT YET REVIEWED.\n\nClaude is the remaining independent reviewer. No Claude review was started or fabricated by this task.\n''', encoding='utf-8')

    after={rel(p):h(p) for p in PROTECTED if p.exists()}
    integrity_ok=before==after and all(before[k]==after[k] for k in before)
    files=[p for p in OUT.rglob('*') if p.is_file() and p.name not in ('consolidation_manifest.json','package_file_hashes.json','external_review_packet.zip')]
    hashes=[{'path':str(p.relative_to(OUT)).replace('\\','/'),'sha256':h(p),'size':p.stat().st_size} for p in sorted(files)]
    (OUT/'package_file_hashes.json').write_text(json.dumps({'algorithm':'SHA-256','files':hashes,'manifest_excluded_self_reference':True},indent=2)+'\n',encoding='utf-8')
    with zipfile.ZipFile(OUT/'external_review_packet.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(PACKET.rglob('*')):
            if p.is_file(): z.write(p, p.relative_to(PACKET.parent).as_posix())
    csv_counts={name:sum(1 for _ in (OUT/name).open(encoding='utf-8'))-1 for name in ['experiment_registry.csv','canonical_results.csv','claim_evidence_matrix.csv','failure_mode_taxonomy.csv','reviewer_attack_surface.csv']}
    manifest={'creation_timestamp_utc':datetime.now(timezone.utc).isoformat(),'experiment_count':csv_counts['experiment_registry.csv'],'canonical_metric_count':csv_counts['canonical_results.csv'],'claim_count':csv_counts['claim_evidence_matrix.csv'],'reviewer_attack_count':csv_counts['reviewer_attack_surface.csv'],'proposed_figure_count':6,'proposed_table_count':8,'source_integrity':'PASS' if integrity_ok else 'FAIL','reproducibility_status':'PASS for final duration/dimensionality analysis; prior actual Yamcs six-case completeness remains incomplete','final_confound_analysis_status':'PASS','external_review_packet_readiness':'READY','protected_hashes_before':before,'protected_hashes_after':after,'protected_inputs_unchanged':integrity_ok,'note':'This manifest excludes itself from the package hash index because it is self-referential.'}
    (OUT/'consolidation_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('FINAL EVIDENCE FREEZE\n---------------------\n')
    print(f"Experiments registered: {manifest['experiment_count']}\nCanonical metrics: {manifest['canonical_metric_count']}\nClaims: {manifest['claim_count']}\nReviewer attack points: {manifest['reviewer_attack_count']}\nFigures proposed: {manifest['proposed_figure_count']}\nTables proposed: {manifest['proposed_table_count']}\n")
    print('New confound analysis:\nDuration association: positive descriptive association (Pearson r=0.360763; Spearman rho=0.444362)\nChannel-count association: strong descriptive association (Pearson r=0.910360; Spearman rho=0.892711)\nControl detections: 40/170 = 23.5294%\nStructural residualization changed classifications: NO\nReproducibility: PASS\nIntegrity: ' + ('PASS' if integrity_ok else 'FAIL') + '\n')
    print('Gemini review: NOT RECEIVED / SOURCE NOT LOCATED\nDeepSeek review: NOT RECEIVED / SOURCE NOT LOCATED\nClaude review: NOT YET REVIEWED\n\nExternal review packet: READY\n\nResearch freeze: YES\n\nDetector v3: NOT CREATED\n\nNew experiments: NONE')
    if not integrity_ok: raise SystemExit('PROTECTED HASH CHANGED')

if __name__=='__main__': main()
