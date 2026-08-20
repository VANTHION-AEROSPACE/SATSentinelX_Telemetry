# Yamcs replay demonstration report

The local Yamcs-compatible parameter replay was configured for six deterministic cases using real ESA Mission-1 selected-channel telemetry. It preserved UTC timezone-naive mission timestamps, channel ordering, values, missing values, and the preceding 3600-second v1 context. The authoritative frozen Detector v1 was imported without modification.

All six cases completed: id_118 impulsive, id_109 short, id_172 medium, id_185 long/persistent high-dimensional, control_0001 difficult `LABEL_NEGATIVE_UNLABELLED`, and control_0069 high-dimensional `LABEL_NEGATIVE_UNLABELLED`. Controls are not normal, healthy, nominal, or confirmed anomalies.

The replay is an operational wrapper demonstration, not a new detector experiment. It does not establish generalization, nominal-control specificity, or operational flight readiness. No threshold tuning, retraining, detector modification, or Detector v3 work occurred.

The local implementation emits explicit Yamcs-style parameter packets and is ready to be connected to an actual Yamcs server configuration in a subsequent integration task.
