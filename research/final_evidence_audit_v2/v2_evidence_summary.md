# Detector v2 evidence summary

V2 was proposed as a separate interpretable research artifact after ESA characterization identified apparent dimensionality accumulation, persistence/duration effects, synchrony, regime changes and scale-provenance issues. It was not used to alter v1, and OPSSAT was excluded from development and threshold selection.

## Formula

For each channel, `z_i = min(abs(x_i - baseline_median) / scale, 20)`. Channel quantities are `d=max(z)/10`, `p=.4*fraction(z>=2)+.4*fraction(z>=3)+.2*fraction(z>=5)`, and scale quality `q` with fixed values 1.0 for MAD, .85 for median-absolute-difference/IQR, .70 for standard deviation and .50 for absolute tolerance. Directional agreement is the dominant sign fraction among meaningful channels. Top-k aggregation uses `k=max(1, ceil(sqrt(n_available)))`. The fixed event score is `score=.35D+.25P+.15A+.10F+.15Q-.20*regime_penalty`, clipped to [0,1]. Primary threshold is 0.60 and strong threshold is 0.75.

## Result

On the same 30 positives and 60 label-negative/unlabelled controls, full v2 reported TP=29, FP=22, TN=38, FN=1, precision=.5686, recall=.9667, FPR=.3667, F1=.7160 and balanced accuracy=.8000. Frozen v1 reported TP=30, FP=22, TN=38, FN=0, F1=.7317 and balanced accuracy=.8167. V2 therefore did not reduce FP and lost one positive.

Ablations were descriptive: without direction, FP=7 and FPR=.1167 with 29/30 recall; without persistence, FP=8 but recall=.900; without dimensionality, FP=17 with all positives retained. These are not selected operating points or validated improvements. Long/persistent and high-dimensional control behavior remained unresolved.

## Conclusion

V2 did not justify replacing v1. It is informative as a controlled negative result showing that the tested fixed formulation did not solve the observed failure modes. Its reproducibility artifact reports PASS with no changed compared files, subject to its documented exclusion of timestamp-bearing reports and manifests. No Detector v3 is created or justified here.
