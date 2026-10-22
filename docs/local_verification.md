# Local technical verification — 21 October 2026

The existing scheduled task and local pipeline passed a fresh end-to-end execution. All **74 automated tests passed**. Runtime ETL code, SQL view definitions, Power BI visuals/model definitions and existing raw snapshots were preserved. AWS was not contacted or deployed, and no GitHub push or destructive database operation was performed.

| Check | PASS / FAIL | Exact result |
|---|---|---|
| Complete automated suite | **PASS** | 74 run, 74 passed, 0 failures, 0 errors, 0 skipped; external sockets blocked; test logs isolated from the live pipeline log |
| Real Windows scheduled-task execution | **PASS** | Started 23:41:17 London time; task exit 0x00000000; controller SUCCESS at 23:41:20; action, schedule and task definition unchanged |
| Python ETL and PostgreSQL load | **PASS** | 11 Tube lines fetched; 12 status rows transformed/validated/inserted; a line can have more than one status |
| PostgreSQL duplicate replay | **PASS** | Same 12-row CSV replay inserted 0 rows and updated 0 lineage values |
| Monitoring and locking | **PASS** | Correlated run marked SUCCESS; 0 RUNNING audit rows; 0 matching advisory locks after completion |
| Historical lineage and SQL analytics | **PASS** | All 41 retained raw snapshots reconcile to 460 status records and 451 line/time observations across 11 lines; daily totals, severity totals and major union reconcile |
| Power BI source and calculations | **PASS** | PBIR schema/binding/layout/interaction checks; 12 TMDL tables and 17 measures parsed; live global, per-line, daily and distribution DAX checks passed |
| Power BI latest-data freshness | **FAIL — refresh pending** | Queried open import model still has 23 collection times, latest imported observation 13:34 model time; PostgreSQL has 41 collection times, latest 23:41:18 London time |
| Offline AWS infrastructure checks | **PASS** | Existing Terraform 1.13.5/provider installation: fmt -check passed; validate returned valid=true with 0 errors and 0 warnings; no init, plan, apply, AWS login or service request |
| Git staging safety | **PASS** | No files staged; no detected sensitive publication candidates; all 21 exclusion probes pass; both working files and actual Git index blobs are scanned |
| Protected file preservation | **PASS** | All 86 pre-existing protected raw/SQL/Power BI source files match their pre-verification hashes |
| Original interruption's exact initiator | **FAIL — insufficient historical evidence** | Task event history was disabled at the time; the available evidence cannot identify the process or user that sent the interruption |
| Task diagnostic history enabled | **FAIL — administrator access required** | Enable attempt returned Windows Access denied, exit 5; channel remains disabled |

The new tests comprise the prior 66 plus eight publication-safety cases: actual Git ignore behavior, force-staged database backups, force-staged raw data, known-secret disclosure without printing secret values, plain SQL COPY dumps, schema/environment template acceptance, secrets left in the index after cleaning the working file, and PostgreSQL custom dumps under unexpected extensions.

Scheduler investigation:

- The previously observed result 3221225786 is 0xC000013A / STATUS_CONTROL_C_EXIT, an interruption status. The status alone does not identify the sender. [Microsoft NTSTATUS reference](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-erref/596a1078-e883-4972-9bbc-49e60bebca55).
- Windows Power-Troubleshooter event 1 records sleep at 16:01:50 UTC and wake at 22:29:09 UTC: approximately 17:01–23:29 London time. That standby period explains the multi-hour collection gap. It coincides with the interrupted 23:29:10 task attempt; this correlation does not prove that standby itself generated the interruption signal.
- No matching Task Scheduler operational events were available because the channel was disabled. Available application events did not establish a Python/pipeline crash as the cause. No evidence justified changing ETL error handling, the Python executable, working directory or SQL.
- The existing task uses the correct virtual-environment Python, quoted controller path and project working directory. It has hourly repetition, StartWhenAvailable, WakeToRun, IgnoreNew overlap handling, no battery stop/start restriction, and no idle-only requirement. Its 72-hour execution limit cannot explain immediate cancellation of a short run. StopOnIdleEnd does not establish a cause when the task is not configured to run only when idle.
- The task uses InteractiveToken, so execution while logged off has not been established. Laptop sleep and logoff are operating constraints; a successful manual task dispatch does not demonstrate future sleep/wake behavior or 24/7 availability.
- Subsequent successful executions were present before this verification, and the controlled Start-ScheduledTask execution also passed. The task definition remained byte-for-byte equivalent after XML normalization. There is no demonstrated persistent script or task-action fault to repair.

The task XML and prior diagnostic-channel configuration were backed up under ignored `backups/local_verification_20261021/`. The attempt to enable the existing operational channel used `wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true`; Windows denied it even outside the workspace sandbox. Administrator access is required. This did not modify the task or its schedule, and it cannot reconstruct missing past events. No further privilege workarounds were attempted.

Necessary corrections made:

1. Added `.gitignore` rules for common database dumps/backups and standalone credential/secret exports. Existing datasets/backups were not removed.
2. Extended `scripts/security_review.py` to inspect force-staged sensitive paths, actual index content, data-bearing SQL COPY exports and PostgreSQL custom-dump signatures. It reports file paths rather than secret values and continues to allow the environment template and schema-only SQL reference.
3. Added eight regression tests. Current Git staging was not changed; staging tests used isolated temporary repositories.
4. Updated README/testing references and recorded this verification report. No runtime ETL, SQL analytics, Terraform resource definitions, report layout or semantic-model definitions needed modification.

Evidence:

- [Full test totals](validation/local_verification_tests.json)
- [Scheduled-task result](validation/scheduler_run.json)
- [Task investigation and power-event evidence](validation/task_investigation.json)
- [Database run, replay and lock checks](validation/local_pipeline_run.json)
- [Current complete lineage audit](validation/local_audit.json)
- [Protected source/data hashes](validation/local_preservation.json)
- [Git publication review](validation/security_review.json)
- Existing Power BI validation JSON files under `powerbi/validation/` were refreshed with the passing definition and live DAX results.

The latest database snapshot contains 332 Good Service observations and 119 disrupted observations: 73.61% and 26.39% of 451 sampled observations. These are not actual uptime measurements. The open Power BI model still contains an earlier import and was not refreshed or saved during this verification. No visuals were rebuilt.

Remaining actions are limited to enabling task history with Windows administrator access for future diagnosis and refreshing the intended Power BI report to display current data. The precise historical interruption sender is irrecoverable from the logs inspected here. Real AWS runtime behavior, IAM enforcement and deployed alarms remain untested by design; deployment is outside the £0 budget. A clean-machine installation, new-database restore and operation while logged off/asleep were not exercised. No current automated test or database integrity failure remains.
