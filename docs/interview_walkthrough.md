# Interview walkthrough

“I built a local pipeline that samples TfL Tube statuses, retains the raw evidence, loads PostgreSQL history, and presents sampled reliability in Power BI. I also implemented optional S3 archival and tested it with Moto, then prepared a serverless Terraform design without deploying paid cloud services.”

Start a five-minute demonstration with the README and architecture. Explain the business questions, show the PBIP's four global cards and four charts, and apply the Tube Line slicer to the two line charts. Explain why the daily and distribution views retain global scope. Check the displayed latest imported observation before comparing it to current PostgreSQL data.

Then show one historical `source_file` alongside its PostgreSQL records. A collection timestamp is not a disruption start time. A line may report several statuses together, so raw row counts would inflate disruption percentages. The base analytics view collapses those rows into one line/time pair; any non-Good-Service status makes that observation disrupted. Daily dates use London time.

Run `python scripts/run_checks.py` using the project interpreter. The suite blocks outbound socket connections and uses temporary files, mocked database connections and Moto. Distinguish these deterministic tests from the separately recorded live TfL/PostgreSQL run and read-only lineage audit. Do not describe mocked rollback tests as a live database failure exercise.

Explain the controls through concrete failure examples:

- A transient TfL response gets bounded retries and timeouts. A permanent extraction failure stops later stages.
- The controller holds a PostgreSQL session advisory lock; another controller returns exit code 2 rather than starting a second run.
- A load failure rolls back the current transaction, closes its connection and leaves the raw evidence available. The controller records failure and releases its lock.
- Replaying an already loaded CSV inserts zero new status rows because the database enforces the four-column identity.
- Optional S3 failure leaves local ETL running and records a sanitized replay-needed event. The replay CLI returns a failure exit code so an operator can detect it.
- A conditional S3 PUT and content hash make identical snapshot replays idempotent. Readback detects corrupt bytes even if the metadata claims the original hash.

For cloud architecture, open `infra/aws/main.tf` and the deployment diagram. Explain the Lambda handler, scoped object-prefix IAM, optional secret reference, disabled scheduling, retained failure queues and bounded logs. Show that the actual ZIP is built by a repository script. Terraform validation proves configuration compatibility, not successful IAM authorization, runtime networking or deployed behavior.

Discuss the important tradeoffs candidly: irregular samples cannot establish uptime or incident durations; the local filename convention has second-level resolution and DST ambiguity; the CSV is a latest-snapshot staging artifact; only the first validity period is flattened; the existing report requires import refresh; there is no cloud database consumer or automatic S3 replay queue. With more time and an approved budget, prioritize timezone-aware collection identifiers, a durable manifest/recovery queue, explicit freshness monitoring and reproducible runtime integration checks.

Use evidence-backed resume wording: “Implemented a Python/PostgreSQL transit analytics pipeline with historical lineage, locking, monitoring and 66 passing automated tests; preserved an existing Power BI dashboard; built checksum-verified Boto3 archival validated with Moto; authored locally validated Terraform for future serverless ingestion.” Do not claim a real AWS deployment, production operations at scale, actual TfL uptime, or Educate completion without evidence.
