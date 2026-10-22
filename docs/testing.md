# Testing and verification

Publication verification, 22 October 2026: **99 Python tests passed, 0 failures, 0 errors, 0 skipped**, with external sockets forbidden. The three additional checks reject force-staged Terraform inputs/plans/provider caches, logs/certificate containers/local data, and oversized files. All **3 Terraform mocked-plan tests passed, 0 failures, 0 errors, 0 skipped**; formatting and schema validation passed with 0 errors/warnings. PBIR validation passed for 14 visuals and TOM parsed 12 tables/17 measures. Current evidence: [Python totals](validation/tests.json), [publication review](publication_review.md), and [publication evidence](validation/publication_review.json). No live pipeline run, database write, dashboard refresh/rebuild, AWS deployment or GitHub push was needed for this publication review.

Latest AWS preparation, 22 October 2026: **96 Python tests passed, 0 failures/errors/skips**, plus **3 Terraform mocked plan tests passed, 0 failures/skips**. This includes the prior 74-test local baseline, 18 new HTTP/Scheduler/execution-registry checks and four isolated download checks. See [AWS readiness](aws_readiness.md), [final Python evidence](validation/aws_tests.json), [Terraform mock evidence](validation/terraform_offline_tests.json), and [package evidence](validation/lambda_package.json). A real account-backed plan and AWS execution were not performed; no credentials/profile are configured. Earlier verification results below remain historical records.

The subsequent [local verification](local_verification.md), completed later on 21 October 2026, passed **74 tests, 0 failures, 0 errors, 0 skipped**: the 66 tests below plus eight Git publication-safety tests. It also passed a real Windows scheduled-task execution, duplicate database replay, complete current lineage reconciliation, Power BI parsing/live DAX, and offline Terraform validation. Exact current results are in [local_verification_tests.json](validation/local_verification_tests.json). Task history could not be enabled because Windows denied administrator-level access; the original interruption's sender remains unknown. The earlier completion results below are retained as historical evidence.

Verification was performed on 21 October 2026 using the existing Python 3.13 virtual environment and local PostgreSQL 18 installation. The original baseline was **43 passed, 0 failed**. The final suite is **66 passed, 0 failures, 0 errors, 0 skipped**. The complete run blocks external socket connections; S3 requests are intercepted by Moto with dummy credentials.

| Automated coverage | Count | Evidence boundary |
|---|---:|---|
| Original ingestion, transformation, quality, loading, controller and monitoring | 43 | Temporary files, mocked HTTP/DB/processes; subprocess quality checks |
| New S3 configuration, uploads, metadata, checksum, replay, corruption, retries, races and Lambda/Moto round trip | 19 | Moto S3 plus injected failures; no real AWS endpoints |
| New Lambda disabled mode, event lineage, sanitized failures and ingestion key redaction | 4 | Mocked TfL/secret/store dependencies |

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/run_checks.py
```

The script writes machine-readable [test totals](validation/tests.json) and an ignored detailed log under `logs/completion_tests.log`. Standard unittest discovery with `-s tests` is also supported. The legacy exploratory API scripts under `src/` are outside the test suite and are not the production controller entry point.

Separate integration/inspection checks actually executed:

| Check | Observed result |
|---|---|
| Full live pipeline, S3 explicitly disabled | Passed at 14:39 London time; 11 TfL line objects, 11 validated records, 11 history inserts, successful audit and lock release |
| Initial sandbox-restricted live attempt | Failed at extraction, recorded FAILED, released lock; preserved in monitoring as truthful failure evidence |
| Read-only all-source audit | Passed: all 29 raw source files loaded, 324 history records, 319 distinct line observations, 29 collection times, 11 lines |
| KPI reconciliation | 236 Good Service + 83 disrupted = 319; 73.98% / 26.02%; daily totals, severity totals and major union match |
| Loader replay | Latest CSV replay inserted 0 rows and changed no lineage |
| Missing historical snapshot recovery | Existing 15 October 22:06:05 raw file loaded through isolated staging; 12 rows inserted; current processed CSV preserved |
| Original two-source lineage verifier | Both original historical sources passed |
| Existing PBIR validator | Cached Microsoft schemas, bindings, formatting, bounds, interactions and original partition/pointer/cache preservation passed |
| Existing TMDL/TOM parser | 12 tables, 17 measures parsed; no active bidirectional relationship |
| Live DAX against an open Desktop engine | Passed global, per-line, daily and distribution queries and global-card invariance; imported 23 collection times, 11 lines, 73.1225% Good Service |
| Terraform | 1.13.5; backend-free initialization; signed AWS provider 6.69.1; fmt and validate passed |
| Lambda package | Local ZIP built; handler/Requests/Boto3 imported with `python -I -S` using only ZIP dependencies |
| Publication candidate review | No detected embedded secrets, caches, data, state or files over 10 MiB; tracked file count initially zero |

The database and Desktop engine were inspected at different refresh points. The queried import model's latest observation was 13:34 model time, earlier than the 14:39 live ETL snapshot. This session verified calculations without refreshing or saving the report. A Desktop refresh is necessary to display current database totals. No current screenshot, visual-rendering review, PBIX inspection or Power BI service refresh was performed. No PBIX or screenshot existed in this workspace.

The initial audit found one retained raw snapshot without a loaded-source reference. It was backfilled through the existing transformer and transactional loader using a separate staging CSV; no existing history was deleted or rewritten. All 29 retained raw files now reconcile. Database audits use a repeatable-read, read-only transaction. Subsequent scheduled runs can change counts, so the JSON is timestamped.

Commands for local engineering checks:

```powershell
.\.venv\Scripts\python.exe scripts/audit_project.py
.\.venv\Scripts\python.exe src/quality/verify_historical_lineage.py
.\.venv\Scripts\python.exe powerbi/tools/validate_dashboard.py
powershell -NoProfile -ExecutionPolicy Bypass -File powerbi/tools/validate_model.ps1
.\.venv\Scripts\python.exe scripts/build_lambda.py --installed
terraform -chdir=infra/aws fmt -check -recursive
terraform -chdir=infra/aws validate
.\.venv\Scripts\python.exe scripts/security_review.py
```

The Power BI scripts rely on installed Desktop/TOM libraries; live DAX additionally requires the correct local engine port and Windows authentication. The preservation validator relies on workstation-specific ignored backups/caches. Script execution policy was bypassed only for the individual validation process, without changing system policy.

Limits: Moto does not prove real IAM enforcement, bucket-policy behavior or production retry timing. No real AWS service calls, Terraform plan/apply, Lambda Linux runtime, clean dependency installation, new-database restore, scheduled future execution, laptop sleep recovery, or forced live database rollback were claimed. Existing unit tests exercise database error/transaction paths through mocks. The security review covers current publication candidates and known local secret values, not an exhaustive enterprise security audit.
