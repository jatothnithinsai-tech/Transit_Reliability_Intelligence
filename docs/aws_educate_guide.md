# Free AWS Educate practice

[AWS Educate](https://aws.amazon.com/education/awseducate/) offers free beginner learning and hands-on labs with email registration and no credit card. Its public catalog currently lists storage, compute, networking, databases and cloud operations; the storage path includes S3. The operations path also lists cost-estimation practice. Catalog checked 21 October 2026. These are learning opportunities, not project deployment evidence.

Register through the official Educate page, choose the catalog's free course/lab, and launch only the supplied learning environment. Do not enter this project's real `.env`, PostgreSQL password, TfL key, or personal AWS access keys into a lab.

| Skill to practice | Exercise to attempt within the supplied lab permissions | Relation to this project |
|---|---|---|
| S3 | Start with the storage course. Upload a harmless sample JSON, inspect metadata, download and compare its hash. Inspect access settings if permitted. | Raw landing zone, source lineage and integrity |
| IAM | Search the signed-in free catalog for IAM/security content. Where a lab permits it, inspect the supplied role and compare object-prefix permissions with broad administrator access. | Lambda's scoped role; identity and resource policies |
| Lambda | Search for a free Lambda/serverless lab in the signed-in catalog. If available, run its sample function, inspect the handler/event, and reproduce a safe test failure. | EventBridge-compatible entry point and retry behavior |
| Monitoring | Use Cloud Operations, then CloudWatch-specific content if offered. Inspect logs/metrics for the lab's resources and explain a failure signal. | Structured events, Lambda error alarms and freshness checks |

The exercises above are suggested practice tasks, not claims that those exact labs or permissions are available. Public catalog content does not establish a dedicated Lambda, IAM, or CloudWatch lab entitlement. Verify current availability after signing in. Do not open a personal paid account or use a trial requiring a payment method to fill a missing lab; use this repository's free Moto tests for that part instead.

Treat lab sessions as temporary and restricted: follow the displayed time limit, allowed regions/services and reset/persistence rules. Do not assume a bucket, role or Lambda survives session end. Save permitted notes or badges, remove account identifiers from screenshots, and never bypass a lab policy to install this project's Terraform stack. A storage lab's website-publication example is separate from this project's private raw bucket design.

An honest portfolio statement is: “I implemented and tested AWS-compatible S3 archival locally using Boto3 and Moto, prepared Terraform infrastructure, and separately practiced AWS services in Educate labs I completed.” List only exercises actually completed. Do not say the full transit pipeline ran on AWS unless a separately authorized deployment is later performed and evidenced.
