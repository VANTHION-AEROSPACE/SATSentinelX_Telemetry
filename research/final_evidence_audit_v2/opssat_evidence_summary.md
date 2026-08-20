# OPSSAT-AD evidence summary

OPSSAT-AD was acquired to provide an independent external-domain and protocol stress test. The official data contain different channels, fragments, time semantics and benchmark label meanings from ESA Mission-1. The compatibility inspection rejected direct frozen-v1 validation because the ESA v1 input contract and OPSSAT representation do not align.

The separate protocol experiment used a train-nominal per-channel robust protocol with a 99th-percentile threshold. On the held-out test split it reported `robust_max` ROC-AUC=.4833 and PR-AUC=.1950, with TP=0, FP=3, FN=113 and TN=413. Comparator protocols were similarly weak. The protocol and reproducibility manifests report PASS, but this is not evidence that OPSSAT validates v1.

The correct interpretation is: OPSSAT-AD provided an independent domain/protocol stress test that did not demonstrate useful discrimination under the predeclared fragment-level protocol. It exposed transferability and protocol limitations. It did not provide direct external validation of frozen Detector v1. Do not write “OPSSAT validated SATSentinel-X.”
