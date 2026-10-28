# Dashboard redesign decisions

27 October 2026. Presentation-only changes; analytical definitions stay intact.

| Page | Stakeholder | Primary question | Organisation and caveats |
|---|---|---|---|
| Transit Reliability | Transport operations analyst | Where are disruptions more common in the collected observations? | Coverage cards → line comparisons → sampled-day trend → raw status mix. Preserve global/line selector scope and timestamp limitations. |

## Visual standard
- Light neutral canvas, aligned panels, restrained borders, readable Segoe UI/Aptos typography and labels that state the metric population.
- Transit: royal blue, observed-good-service teal, disruption coral and a purple coverage card.
- NHS: healthcare blue, teal, coral and selective purple; independent portfolio branding.
- Hospitality: warm green, blue and gold. Native objects, formulas and data sources are retained.
- Units and denominators remain visible; colour is supported by text labels. No generated mockup or rewritten KPI pixels are used.

## Verification limits
Page loading, metadata validation and source fingerprints are distinct from a full usability test. Consult redesign_validation.json for the exact executed checks. Existing historical test evidence is retained separately.
