import pandas as pd

file_path = "data/processed/tube_status_clean.csv"


df = pd.read_csv(file_path)

print("Starting data quality checks...\n")

issues_found = 0

# 1. Check required columns
required_columns = [
    "snapshot_time",
    "line_id",
    "line_name",
    "mode",
    "status_severity",
    "status_description"
]

missing_columns = [col for col in required_columns if col not in df.columns]

if missing_columns:
    print("FAIL - Missing required columns:", missing_columns)
    raise SystemExit(1)
else:
    print("PASS - All required columns are present")

# 2. Check missing IDs
if df["line_id"].isna().any():
    print("FAIL - Missing line_id values found")
    issues_found += 1
else:
    print("PASS - No missing line_id values")

# 3. Check missing line names
if df["line_name"].isna().any():
    print("FAIL - Missing line_name values found")
    issues_found += 1
else:
    print("PASS - No missing line_name values")

# 4. Check missing status descriptions
if df["status_description"].isna().any():
    print("FAIL - Missing status descriptions found")
    issues_found += 1
else:
    print("PASS - No missing status descriptions")

# 5. Check valid severity range
severity = pd.to_numeric(df["status_severity"], errors="coerce")

invalid_severity = df[
    severity.isna() |
    (severity < 0) |
    (severity > 20) |
    (severity % 1 != 0)
]
if not invalid_severity.empty:
    print("FAIL - Invalid status severity values found")
    issues_found += 1
else:
    print("PASS - Status severity values are valid")

# 6. Check duplicate status records
duplicate_columns = [
    "snapshot_time",
    "line_id",
    "status_severity",
    "status_description"
]

duplicate_count = df.duplicated(
    subset=duplicate_columns
).sum()

if duplicate_count > 0:
    print(f"FAIL - {duplicate_count} duplicate status records found")
    issues_found += 1
else:
    print("PASS - No duplicate status records found")

# 7. Validate snapshot timestamps
parsed_timestamps = pd.to_datetime(
    df["snapshot_time"],
    format="%Y-%m-%d %H:%M:%S",
    errors="coerce"
)

invalid_timestamps = parsed_timestamps.isna().sum()

if invalid_timestamps > 0:
    print(f"FAIL - {invalid_timestamps} invalid snapshot timestamps found")
    issues_found += 1
else:
    print("PASS - All snapshot timestamps are valid")
print("\nData quality validation complete.")

if issues_found == 0:
    print("RESULT: DATA PASSED QUALITY CHECKS")
else:
    print(f"RESULT: {issues_found} critical quality issue(s) found")
    raise SystemExit(1)