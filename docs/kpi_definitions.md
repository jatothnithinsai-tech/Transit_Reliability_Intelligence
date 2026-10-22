# KPI definitions

The denominator for sampled reliability is a **line observation**: one distinct `(line_id, snapshot_time)` pair. It is not the number of raw status rows. One API collection normally contributes 11 observations, while a line with two statuses still contributes one observation.

| Metric | Calculation and scope |
|---|---|
| Total Tube Lines | Distinct lines in the imported global SQL summary; expected 11, not hard-coded in the measure |
| Total Historical Snapshots | Distinct collection timestamps; not the sum of per-line snapshot counts |
| Sampled Good Service % | 100 × observations where **all** statuses have severity 10 / all line observations |
| Sampled disruption % | 100 × observations where **any** status has severity other than 10 / all line observations |
| Line Good Service % | Same observation calculation for the selected line; sum numerators / sum denominators |
| Daily disruption % | Disrupted line observations / total line observations on each Europe/London date, multiplied by 100 |
| Status distribution | Count of raw status records by description; denominator differs from observation KPIs |
| Major disruptions by line | Count of line/time pairs containing Severe Delays, Part Closure, Part Suspended or Planned Closure |

If a line reports Good Service and Severe Delays at the same collection time, it is one disrupted observation and zero Good Service observations. BOOL_OR/BOOL_AND in the base SQL view enforce this distinction. The global counts reconcile to the daily counts and the good/disrupted flags are complementary for the validated data.

Major-category counts overlap. A line/time with Severe Delays and Part Suspended contributes once to each category but only once to the major union. The selected categories are a project business definition; they are not an exhaustive TfL incident taxonomy and do not include every possible full-closure/suspension label. Numeric severity codes are categories, so averaging them would not produce a meaningful severity index.

SQL percentage columns already use a 0–100 scale. TMDL uses `0.00\%`, a literal percent symbol, so 75.00 displays as 75.00%. DAX measures that divide raw counts multiply the ratio by 100 once. Do not apply a normal percentage format that scales by 100 again, multiply an existing SQL percentage by 100, or average already-rounded line percentages to get a global value.

The four global KPI cards remain global under Tube Line selection. The two line-level charts respond to the slicer; the daily trend and status distribution retain their global aggregate scope. This is explicitly encoded in PBIR interactions and verified by the existing validator.

Sampling frequency is uneven and gaps exist. These measures cannot establish actual uptime, passenger experience, incident duration, unique incident counts, or contractual SLA compliance. A status observed on three hourly samples is three observations, not proof of a three-hour incident. Planned closures count as disruptions under the stated definition.
