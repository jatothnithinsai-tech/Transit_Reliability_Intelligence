"""Estimate the reviewed hourly workload from public London price-list files.

Default: cached/offline calculation. --refresh downloads public unsigned JSON
from AWS's price-list website; it never authenticates or provisions anything.
"""
import argparse
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
from urllib.request import urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REGION = "eu-west-2"
SERVICES = ["AmazonCloudWatch", "AWSLambda", "AmazonS3"]


def rate(document, usage):
    choices = []
    for sku, product in document["products"].items():
        if product["attributes"].get("usagetype") != usage:
            continue
        for term in document.get("terms", {}).get("OnDemand", {}).get(sku, {}).values():
            for dimension in term["priceDimensions"].values():
                if Decimal(dimension.get("beginRange", "0")) == 0:
                    choices.append({"usd": dimension["pricePerUnit"]["USD"], "unit": dimension["unit"],
                                    "description": dimension["description"], "sku": sku})
    if len(choices) != 1:
        raise ValueError(f"Expected one first-tier rate for {usage}; found {len(choices)}")
    return choices[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    cache = ROOT / ".tools/aws-pricing"
    documents, sources = {}, {}
    for service in SERVICES:
        url = f"https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/{service}/current/{REGION}/index.json"
        path = cache / f"{service}-{REGION}.json"
        if args.refresh:
            cache.mkdir(parents=True, exist_ok=True)
            with urlopen(url, timeout=30) as response:
                body = response.read(32 * 1024 * 1024)
            parsed = json.loads(body)
            path.write_bytes(body)
        else:
            parsed = json.loads(path.read_text())
        documents[service] = parsed
        sources[service] = {"url": url, "publication_date": parsed.get("publicationDate")}
    selections = {
        "alarm": ("AmazonCloudWatch", "EUW2-CW:AlarmMonitorUsage"),
        "metric": ("AmazonCloudWatch", "EUW2-CW:MetricMonitorUsage"),
        "logs_ingestion": ("AmazonCloudWatch", "EUW2-DataProcessing-Bytes"),
        "lambda_duration": ("AWSLambda", "EUW2-Lambda-GB-Second"),
        "lambda_requests": ("AWSLambda", "EUW2-Request"),
        "s3_storage": ("AmazonS3", "EUW2-TimedStorage-ByteHrs"),
        "s3_put": ("AmazonS3", "EUW2-Requests-Tier1"),
        "s3_get": ("AmazonS3", "EUW2-Requests-Tier2"),
    }
    rates = {name: rate(documents[service], usage) for name, (service, usage) in selections.items()}
    value = lambda name: Decimal(rates[name]["usd"])
    runs = Decimal(720)
    costs = {
        "cloudwatch_alarms": 4 * value("alarm"),
        "cloudwatch_custom_metric": value("metric"),
        "cloudwatch_log_ingestion": Decimal(5) / 1024 * value("logs_ingestion"),
        "lambda_compute": runs * 2 * Decimal("0.125") * value("lambda_duration"),
        "lambda_requests": runs * value("lambda_requests"),
        "s3_steady_raw_and_control_storage": Decimal("0.042") * value("s3_storage"),
        "s3_put_requests": runs * 3 * value("s3_put"),
        "s3_get_requests": runs * value("s3_get"),
        "scheduler_gross_reference_rate": runs / 1000000,  # Official $1/M example, no free deduction.
    }
    result = {"checked_at_london": datetime.now(ZoneInfo("Europe/London")).isoformat(),
              "region": REGION, "currency": "USD", "free_tier_deductions": 0,
              "assumptions": {"runs_per_30_day_month": 720, "average_lambda_seconds": 2,
                "lambda_memory_mb": 128, "snapshot_kib": 20, "raw_retention_days": 90,
                "control_retention_days": 7, "custom_metrics": 1, "alarms": 4},
              "regional_rates": rates, "monthly_components_usd": {k: str(v) for k, v in costs.items()},
              "monthly_subtotal_usd": str(sum(costs.values())), "planning_allowance_usd": [1, 3],
              "sources": sources,
              "exclusions": ["tax and currency conversion", "retries/failures and extra downloads",
                "small log-retention/SQS/SNS usage", "optional Secrets Manager (~$0.40 plus reads)",
                "growth beyond the stated workload"],
              "account_eligibility": "Unverified; no usable AWS credentials or profile available"}
    target = ROOT / "docs/validation/aws_cost_estimate.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"region": REGION, "monthly_subtotal_usd": str(sum(costs.values())),
                      "planning_allowance_usd": [1, 3], "rates_found": len(rates)}))


if __name__ == "__main__":
    main()
