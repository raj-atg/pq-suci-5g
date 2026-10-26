# Invalid runs: AUSF context pool exhausted

These attach-storm runs failed with `FIVEG_SERVICES_NOT_ALLOWED` because the Open5GS AUSF ran out
of UE contexts (`ogs_pool_id_calloc() failed`, `src/ausf/context.c:138`, see `ausf.log`). The
AUSF keeps one context per SUCI string; every protected registration uses a fresh SUCI and the
test UEs were stopped without deregistering, so contexts piled up until the pool (`max.ue`, 1024)
was full. They are kept as evidence and excluded from the results. The runs were repeated with a
core restart before each scheme (`experiments/e4_storm.sh`).
