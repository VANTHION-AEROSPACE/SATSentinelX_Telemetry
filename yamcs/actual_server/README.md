# SATSentinel-X actual Yamcs integration

This package is an isolated Yamcs 5.13.2 integration for the six pre-approved replay cases. It uses the official `yamcs/example-simulation:5.13.2` image, but does not use the image's synthetic simulator data. Real ESA Mission-1 selected-channel values are sent to Yamcs through its JSON UDP Parameter Data Link and read back from the Yamcs processed-parameter path before invoking the immutable Detector v1.

The mapping is identity-valued:

`ESA channel_N -> /SATSENTINEL_X/ESA/channel_N -> Detector channel_N`

Mission timestamps are sent as Yamcs generation times in UTC and converted back to the existing detector convention: UTC timezone-naive timestamps. NaN values are not sent as parameter updates and remain missing in the detector-equivalent reconstruction, matching the existing adapter's finite-value semantics.

No detector, threshold, label, case selection, or prior result is modified.
