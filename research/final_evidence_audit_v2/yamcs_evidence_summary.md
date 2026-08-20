# Actual Yamcs evidence summary

The actual deployment used Yamcs 5.13.2 in Docker image `yamcs/example-simulation:5.13.2`, container `satsentinel-yamcs-esa`, image digest `sha256:cd184d1627996da0f13ded33673426e574beebb7a4a699532b2f1cf0c47fc17a`, instance `satsentinel_x`, and realtime processor `realtime`. The XTCE file `mdb/satsentinel-x-esa.xml` loaded 26 parameters. The configured UDP Parameter Data Link `esa_pp_realtime` listened on UDP 11016 and reached status OK with zero invalid datagrams in the recorded run.

The smoke test demonstrated ESA channel 41 -> `/SATSENTINEL_X/channel_41` -> retrieved Yamcs parameter. Source and Yamcs values were exactly `0.9624888896942139`, and generation time `2007-05-22T05:30:06.120Z` was preserved.

The local deterministic Yamcs-compatible replay passed all six fixed cases as a contract reference. The actual Yamcs replay then passed score equivalence for five of six cases: id_118, id_109, id_172, id_185 and control_0001. `control_0069` did not have complete Parameter Archive coverage; its recorded source end was `2002-10-16T15:29:01.888`, while Yamcs history ended at `2002-10-16T15:28:55.242Z`, producing a score delta of `0.0029166666666666785`.

A targeted readiness gate polled the actual bulk archive export and required per-channel source row-count equality plus final-timestamp coverage before invoking v1. It timed out after 300 seconds / 48 polls on case_04, with representative deficits such as channel 12: 2164 source vs 2133 Yamcs rows, channel 41: 6818 vs 6721, and channel 47: 6493 vs 6398. The logs showed repeated `ParameterArchive-backfilling_*` ReplayService processors and `parchive.getRealtimeFiller: null`. Thus six-of-six equivalence is not established.

Actual Yamcs integration was demonstrated, but operational validation is not established. The archive failure is itself a practical deployment/integration lesson.
