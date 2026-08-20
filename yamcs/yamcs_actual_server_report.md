# Actual Yamcs server integration report

**Status: YAMCS_SERVER_BLOCKED.**

No actual Yamcs server was used. No Yamcs version was available locally. Java 17 and Docker 28.0.1 are installed, but Docker Desktop is not running: `com.docker.service` is stopped and the Docker named pipe is unavailable. `docker pull yamcs/example-simulation:5.13.2` failed with a missing `dockerDesktopLinuxEngine` pipe. `docker desktop start` timed out because Docker could not create its host log files due to access denial.

The six fixed cases, real-telemetry adapter, channel mapping, frozen v1 integration, and validated adapter equivalence remain prepared. The actual Yamcs pipeline was not executed, so no actual-server equivalence, operator-view, replay, or two-run result is claimed.
