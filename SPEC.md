# Data Janitor Assessment v0.1
**Status:** Draft Baseline  
**Version:** 0.1  
**Product type:** Productized assessment with a lightweight local execution harness  
**Primary goal:** Prove that a repeatable data-health assessment can identify, prioritize, and communicate material data problems using evidence rather than subjective consulting judgment.

---

# 1. Product Definition

Data Janitor Assessment is a structured assessment for identifying data problems that can undermine analytics, automation, operational reporting, and AI initiatives.

The assessment must convert technical evidence into a prioritized business-facing diagnosis.

It is not intended to answer:

> “Is this database technically perfect?”

It is intended to answer:

> “What problems in this data environment are most likely to make analytics, automation, or AI unreliable, risky, or unnecessarily expensive?”

The assessment consists of:

1. a repeatable methodology;
2. automated and manual evidence collection;
3. a standardized scoring model;
4. prioritized findings;
5. a standardized executive report.

---

# 2. v0.1 Product Thesis

Many organizations already have databases, dashboards, pipelines, and increasing pressure to use AI.

Their problem is often not lack of technology.

Common underlying problems include:

- duplicate business entities;
- inconsistent business metrics;
- missing documentation;
- unclear ownership;
- unknown or exposed PII;
- stale datasets;
- broken relationships between datasets;
- unreliable pipelines;
- conflicting definitions of the same business concept.

These problems are frequently discovered only after they affect reporting, automation, or AI initiatives.

Data Janitor attempts to identify them earlier and present remediation priorities in a form that both technical teams and management can understand.

---

# 3. v0.1 Goals

v0.1 must prove five things.

### G1 — Repeatability

A new dataset can be assessed using the same methodology without redesigning the framework.

### G2 — Evidence-based findings

Every finding must contain observable evidence.

No finding may exist only because:

> “the assessor thinks this looks bad.”

### G3 — Business translation

Technical findings must explain why they matter operationally.

Example:

Bad:

> `customer_id uniqueness = 91.4%`

Good:

> Approximately 8.6% of customer identifiers are duplicated or reused. This can inflate customer counts, distort segmentation, and create incorrect joins between sales and customer datasets.

### G4 — Prioritization

The product must distinguish between:

- cosmetic problems;
- technical debt;
- operational risk;
- material blockers.

### G5 — Independent credibility

The entire v0.1 benchmark, methodology, code, report, and public demonstration must be independently created using synthetic or properly licensed public data.

No employer:

- code;
- schema;
- dataset;
- query;
- document;
- template;
- internal metric;
- proprietary process;
- confidential example

may be used.

---

# 4. Explicit Non-Goals

v0.1 is **not**:

- a full SaaS application;
- a data catalog;
- an observability platform;
- a replacement for dbt;
- a replacement for Great Expectations;
- a master-data-management platform;
- a cybersecurity audit;
- a legal compliance audit;
- an Indonesian PDP compliance certification;
- an AI governance platform;
- an architecture review;
- a cloud-cost assessment;
- a BI implementation service;
- a data-engineering consulting marketplace;
- an automated remediation platform.

v0.1 does not modify customer data.

All assessment operations must be read-only.

---

# 5. Target User

Primary users:

- Head of Data;
- Data Manager;
- CTO;
- technical founder;
- analytics lead;
- engineering leader.

Secondary audience:

- CFO;
- COO;
- CEO;
- transformation leader.

The technical user needs evidence.

The executive user needs:

- risk;
- impact;
- priority;
- remediation direction.

The product must serve both without generating two separate assessments.

---

# 6. v0.1 Deliverables

v0.1 is not complete until all four product assets exist.

## Deliverable A — Synthetic Benchmark

A fictional organization with intentionally imperfect data.

Purpose:

- test the methodology;
- validate checks;
- generate sample findings;
- provide reproducible public proof.

## Deliverable B — Assessment Methodology

Canonical definition of:

- assessment dimensions;
- checks;
- evidence;
- scoring;
- severity;
- prioritization;
- manual review;
- report generation.

## Deliverable C — Sample Assessment Report

A complete executive-quality assessment generated from the synthetic benchmark.

It must be clearly labeled:

**Synthetic demonstration — not a real client engagement.**

## Deliverable D — Public Proof Package

Public-facing material containing:

- methodology overview;
- synthetic benchmark description;
- example findings;
- sample report;
- explanation of what Data Janitor evaluates;
- explicit synthetic-data disclosure.

A simple GitHub repository + GitHub Pages/static landing page is sufficient.

---

# 7. Execution Model

v0.1 must contain a lightweight execution harness.

It does **not** need to be production SaaS.

Conceptual flow:

```text
Input Data
    ↓
Dataset Profiling
    ↓
Automated Checks
    +
Manual / Evidence-Based Checks
    ↓
Normalized Findings
    ↓
Scoring
    ↓
Risk Prioritization
    ↓
AI Readiness Gate
    ↓
Assessment Report
```

The execution harness exists to prove repeatability.

It must not become a platform-engineering project.

---

# 8. Required Input Support

Required for v0.1:

- CSV;
- Parquet;
- DuckDB.

Optional stretch:

- PostgreSQL read-only connection.

Not required:

- BigQuery;
- Snowflake;
- Redshift;
- SQL Server;
- MySQL;
- SaaS connectors.

Connector breadth is explicitly deferred.

---

# 9. Local-First Requirement

The benchmark and assessment must be runnable locally.

No mandatory:

- cloud service;
- commercial API;
- LLM API;
- external data upload

may be required.

An LLM may optionally assist with:

- explanation;
- summarization;
- remediation wording.

However:

**the assessment must remain functional when LLM functionality is disabled.**

No raw assessment data should be sent to an external AI service by default.

---

# 10. Assessment Dimensions

Data Janitor v0.1 evaluates six dimensions.

| Dimension | Weight |
|---|---:|
| Data Quality | 25% |
| Metadata & Documentation | 15% |
| Metric Consistency | 15% |
| Privacy & PII Hygiene | 15% |
| Ownership & Governance | 15% |
| Reliability & Freshness | 15% |
| **Total** | **100%** |

The weights are product heuristics for v0.1.

They are not claimed to be an industry-standard or scientifically validated scoring model.

---

# 11. Dimension 1 — Data Quality

**Weight: 25%**

Purpose:

Determine whether core data is sufficiently accurate, complete, internally consistent, and structurally reliable.

### DQ-01 — Key Uniqueness

Check whether fields expected to uniquely identify records actually do so.

Examples:

- customer ID;
- invoice number;
- order ID;
- product ID.

### DQ-02 — Duplicate Business Entities

Detect probable duplicate real-world entities even when IDs differ.

Examples:

```text
Toko Makmur
TOKO MAKMUR
Toko Makmur.
TOKO MAKMUR JAYA
```

The benchmark should include obvious and fuzzy duplicates.

### DQ-03 — Critical Field Completeness

Measure NULL, blank, invalid-default, or missing values in business-critical fields.

### DQ-04 — Referential Integrity

Identify records referencing entities that do not exist.

Example:

```text
orders.customer_id
```

that has no matching record in:

```text
customers.customer_id
```

### DQ-05 — Domain Validity

Check values against expected domains.

Examples:

```text
status = "ACTIVE", "INACTIVE"
```

rather than:

```text
A
Active
active
1
ACT
```

unless explicitly mapped.

### DQ-06 — Range and Logical Validity

Identify impossible or highly suspicious values.

Examples:

- negative quantity;
- impossible dates;
- invalid percentage;
- zero-price transactions where not allowed.

### DQ-07 — Duplicate Transactions

Detect likely repeated ingestion or duplicated operational events.

### DQ-08 — Cross-Dataset Reconciliation

Compare numbers that should reconcile across related datasets.

Example:

```text
invoice_total
```

versus:

```text
SUM(invoice_lines)
```

---

# 12. Dimension 2 — Metadata & Documentation

**Weight: 15%**

Purpose:

Determine whether people and systems can understand what important data represents and where it comes from.

### MD-01 — Dataset Description

Critical tables or datasets should have a usable description.

### MD-02 — Critical Column Documentation

Important fields should have understandable semantic definitions.

### MD-03 — Source-System Traceability

Important datasets should identify their authoritative source.

### MD-04 — Transformation Traceability

Important derived datasets should document how they are created.

Full automated lineage is not required.

### MD-05 — Dataset Lifecycle Status

Datasets should distinguish between:

- active;
- experimental;
- deprecated;
- obsolete.

### MD-06 — Naming Consistency

Evaluate meaningful consistency in table and field naming.

This check must not penalize stylistic differences purely for aesthetics.

### MD-07 — Business Glossary Linkage

Critical business concepts should have an identifiable business meaning.

Examples:

- Active Customer;
- Revenue;
- Order;
- Churn;
- Gross Sales.

---

# 13. Dimension 3 — Metric Consistency

**Weight: 15%**

Purpose:

Determine whether important business metrics mean the same thing across teams and systems.

### MC-01 — Critical Metric Definition Exists

Critical metrics should have an explicit definition.

### MC-02 — Formula Consistency

Detect multiple conflicting formulas for the same metric.

### MC-03 — Grain Consistency

Metric definitions should specify the level at which they are calculated.

Examples:

- transaction;
- invoice;
- customer-day;
- customer-month.

### MC-04 — Time Basis Consistency

Identify conflicting:

- date fields;
- timezone conventions;
- reporting periods.

### MC-05 — Inclusion / Exclusion Rules

Metrics should define important exclusions.

Examples:

- canceled orders;
- returns;
- vouchers;
- tax;
- discounts.

### MC-06 — Authoritative Source

Critical metrics should identify an approved or preferred source.

### MC-07 — Metric Reconciliation

Where multiple implementations exist, compare their resulting values.

Material divergence becomes a finding.

---

# 14. Dimension 4 — Privacy & PII Hygiene

**Weight: 15%**

Purpose:

Identify avoidable exposure and poor handling of personally identifiable or sensitive data.

This dimension is a **data hygiene assessment**.

It is explicitly **not a legal compliance certification**.

### PP-01 — PII Discovery

Identify fields likely containing:

- full name;
- telephone number;
- email;
- address;
- identity numbers;
- precise location;
- other identifiable information.

### PP-02 — PII Classification

PII should be identifiable as such in metadata or assessment configuration.

### PP-03 — Unnecessary PII Presence

Flag datasets containing high-risk fields that do not appear necessary for their apparent analytical purpose.

This check may require manual confirmation.

### PP-04 — Unprotected Analytical Copies

Identify obvious plaintext PII replicated into analytical extracts or demonstration/non-production datasets.

### PP-05 — Shadow Exports

Identify uncontrolled or poorly documented extracts containing PII where evidence is available.

Example:

```text
customer_export_final_v7.csv
```

### PP-06 — Retention Awareness

Determine whether high-risk datasets have an identifiable retention expectation.

### PP-07 — PII Ownership

Sensitive datasets should have an identifiable responsible owner.

---

# 15. Dimension 5 — Ownership & Governance

**Weight: 15%**

Purpose:

Determine whether important data has accountable human ownership.

### OG-01 — Dataset Owner

Critical datasets should have an identified owner.

### OG-02 — Business Owner

Important business concepts and metrics should have an accountable business owner.

### OG-03 — Criticality Classification

Important datasets should have some form of criticality classification.

Example:

```text
Tier 1 — business critical
Tier 2 — important
Tier 3 — supporting
```

Exact terminology is not prescribed.

### OG-04 — Change Accountability

Critical datasets should have an identifiable process or owner responsible for material schema/logic changes.

### OG-05 — Data Issue Ownership

There should be an identifiable destination for reporting and resolving material data issues.

### OG-06 — Lifecycle Accountability

Deprecated, replaced, and obsolete datasets should have somebody responsible for retirement decisions.

---

# 16. Dimension 6 — Reliability & Freshness

**Weight: 15%**

Purpose:

Determine whether consumers can reasonably depend on important datasets being available and sufficiently current.

### RF-01 — Freshness Expectation

Critical datasets should have an expected update frequency.

### RF-02 — Actual Freshness

Compare actual update timing to the expected timing.

### RF-03 — Pipeline Failure Visibility

Determine whether failed processing can be detected.

### RF-04 — Schema Drift Awareness

Determine whether unexpected structural changes can be discovered.

### RF-05 — Data Volume Anomaly Awareness

Detect or document significant unexpected row-volume changes.

### RF-06 — Duplicate / Reprocessing Protection

Assess whether repeated jobs can generate duplicate business records.

### RF-07 — Recovery Capability

Determine whether failed or late processing has an identifiable recovery/backfill mechanism.

---

# 17. Total Core Checks

v0.1 therefore contains:

```text
Data Quality                  8
Metadata & Documentation      7
Metric Consistency            7
Privacy & PII Hygiene         7
Ownership & Governance        6
Reliability & Freshness       7
                              ──
Total                         42
```

The canonical v0.1 check catalog is frozen at 42 checks.

New checks discovered during development should normally be candidates for v0.2 rather than silently expanding scope.

---

# 18. Check Types

Every check must be labeled as one of:

### Automated

Can be evaluated directly from available data or metadata.

### Manual

Requires human evidence or judgment.

### Hybrid

Automated evidence is produced, but final classification requires human interpretation.

Example:

```text
Duplicate customer candidates
```

may be generated automatically, while confirming whether they are genuinely the same business may require manual review.

---

# 19. Check Definition Schema

Every check must contain at least:

```yaml
id: DQ-02
name: Duplicate Business Entities
dimension: data_quality
mode: hybrid
importance_weight: 5

description:
  Detect probable duplicate real-world business entities.

evidence_required:
  - candidate duplicate count
  - affected record count
  - percentage affected
  - representative examples

business_impact:
  Duplicate entities may distort customer counts,
  segmentation, territory reporting, and downstream joins.

possible_remediation:
  Establish canonical entity identifiers and
  entity-resolution rules.
```

Implementation-specific thresholds must be configurable where appropriate.

---

# 20. Check Status

Each applicable check receives one status:

```text
PASS
PARTIAL
FAIL
UNKNOWN
N/A
```

Definitions:

### PASS

Evidence indicates the expected condition is substantially met.

### PARTIAL

The expected condition exists but is incomplete, inconsistent, or weak.

### FAIL

Evidence demonstrates a material deficiency.

### UNKNOWN

The check is relevant, but sufficient evidence cannot be obtained.

Unknown is itself reported as an evidence gap.

### N/A

The check legitimately does not apply.

N/A checks are excluded from scoring.

---

# 21. Scoring Model

Every check has:

```text
importance_weight = 1–5
```

Status values used in numeric scoring:

```text
PASS      = 1.0
PARTIAL   = 0.5
FAIL      = 0.0
```

UNKNOWN and N/A are excluded from the numeric calculation.

Dimension score:

```text
dimension_score =
100 ×
SUM(check_weight × status_value)
/
SUM(scored_check_weight)
```

Overall score:

```text
overall_score =
Σ(dimension_score × dimension_weight)
```

Result is rounded to the nearest whole number.

---

# 22. Evidence Coverage

A numeric score must never hide the fact that major portions of an environment could not be assessed.

Each dimension therefore also reports:

```text
Evidence Coverage %
```

Example:

```text
Data Quality
Score: 78/100
Evidence Coverage: 95%

Ownership & Governance
Score: 72/100
Evidence Coverage: 43%
```

If evidence coverage is below 75%, the dimension must be marked:

> **Limited evidence**

This prevents missing documentation from accidentally producing an artificially strong score.

---

# 23. Overall Score Interpretation

v0.1 uses the following descriptive bands:

| Score | Classification |
|---:|---|
| 85–100 | Healthy |
| 70–84 | Managed but exposed |
| 50–69 | Fragile |
| 0–49 | High risk |

The report must not claim these bands are universal industry benchmarks.

They are Data Janitor v0.1 internal assessment bands.

---

# 24. Risk Severity

Assessment score and finding severity are deliberately separate.

A finding receives:

```text
Impact:      1–5
Likelihood:  1–5
```

Risk score:

```text
Impact × Likelihood
```

Severity:

| Risk Score | Severity |
|---:|---|
| 1–4 | Low |
| 5–9 | Medium |
| 10–16 | High |
| 17–25 | Critical |

Impact should consider potential:

- financial distortion;
- operational disruption;
- incorrect decision-making;
- privacy exposure;
- reporting failure;
- AI/automation failure.

Likelihood considers how:

- widespread;
- frequent;
- systemic;
- currently observable

the issue is.

---

# 25. Finding Schema

Every material finding must produce a normalized finding record.

Minimum structure:

```json
{
  "finding_id": "DJ-DQ-002",
  "check_id": "DQ-02",
  "dimension": "data_quality",
  "title": "Probable duplicate customer records",
  "status": "FAIL",
  "severity": "HIGH",
  "risk_score": 15,
  "confidence": "HIGH",
  "summary": "4.8% of customer records are probable duplicates.",
  "evidence": {
    "records_affected": 481,
    "percentage": 4.8,
    "examples": []
  },
  "business_impact": [
    "inflated customer counts",
    "incorrect customer segmentation",
    "unreliable customer-level reporting"
  ],
  "recommended_action": "Introduce canonical customer identity and entity-resolution rules.",
  "remediation_horizon": "30_days",
  "automated": true
}
```

---

# 26. Finding Confidence

Findings must distinguish between certainty of evidence and severity.

Confidence values:

```text
HIGH
MEDIUM
LOW
```

Example:

A deterministic duplicate primary key:

```text
Confidence = HIGH
```

A fuzzy entity match:

```text
Confidence = MEDIUM
```

A suspected unused PII field based only on metadata:

```text
Confidence = LOW
```

Low-confidence findings must not be presented as facts.

---

# 27. Prioritization

Findings should be prioritized using:

```text
Severity
+
Business impact
+
Remediation effort
+
Dependency
```

Each finding receives an approximate remediation effort:

```text
LOW
MEDIUM
HIGH
```

This allows identification of:

### Quick wins

High-impact problems with relatively low remediation effort.

### Structural problems

High-impact problems requiring larger organizational or architectural work.

---

# 28. AI Readiness

v0.1 must **not** manufacture a separate pseudo-scientific “AI Readiness Score.”

Instead, it reports:

```text
Data Health Score
+
AI Readiness Status
```

AI Readiness Status can be:

```text
READY
CONDITIONAL
NOT READY
```

The purpose is narrow:

> Is the assessed data environment suitable for becoming a dependable input to consequential AI or automation workflows?

---

# 29. AI Readiness Blockers

Examples of blockers include:

- unresolved critical PII exposure;
- major duplicate key/entity problems in core business entities;
- contradictory definitions for critical metrics;
- materially broken referential integrity;
- critical datasets with unknown provenance;
- critical datasets with uncontrolled freshness;
- repeated pipeline failures without detection;
- insufficient evidence to understand core datasets.

Rules must remain explainable.

The report must explicitly state which findings caused the readiness classification.

---

# 30. Synthetic Benchmark

The v0.1 benchmark represents a fictional B2B distribution company.

Temporary company name:

**Northstar Distribution**

The benchmark must be generic and independently created.

It must not reproduce any real employer schema.

---

# 31. Benchmark Core Datasets

Recommended minimum:

```text
customers
products
orders
order_items
payments
returns
customer_export
metric_definitions
pipeline_runs
dataset_registry
```

Optional:

```text
sales_summary
customer_master_legacy
```

---

# 32. Benchmark Scale

The benchmark should be large enough that profiling feels realistic while remaining trivial to run locally.

Suggested approximate scale:

```text
Customers         10,000
Products           2,000
Orders             50,000
Order Items       150,000+
Payments           45,000+
Returns             5,000+
Pipeline Runs       2,000+
```

Exact row counts are not product requirements.

Reproducibility is more important than size.

---

# 33. Benchmark Required Defects

The synthetic benchmark must intentionally contain known issues across all six dimensions.

Examples include:

### Data Quality

- duplicate customers;
- orphan orders;
- duplicate invoices;
- negative quantity;
- impossible dates;
- missing critical values;
- reconciliation mismatch.

### Metadata

- undocumented tables;
- missing source information;
- poorly documented critical fields;
- deprecated table not marked as deprecated.

### Metrics

Multiple definitions of:

```text
Revenue
Active Customer
Net Sales
```

with intentional contradictions.

### Privacy

- plaintext email/telephone exports;
- unnecessary PII replication;
- sensitive dataset without owner;
- unclear retention.

### Governance

- critical datasets without owners;
- multiple apparent sources of truth;
- obsolete dataset still available.

### Reliability

- stale datasets;
- simulated pipeline failures;
- duplicate ingestion event;
- irregular data volumes;
- missing freshness expectation.

---

# 34. Benchmark Ground Truth

Synthetic generation must also produce a private or test-only ground-truth manifest.

Example:

```json
{
  "expected_issues": [
    "duplicate_customers",
    "orphan_orders",
    "revenue_definition_conflict",
    "unowned_pii_export"
  ]
}
```

The assessment engine must **not** read this manifest during execution.

Its purpose is QA.

This provides a way to determine whether Data Janitor actually detects the defects deliberately introduced into the benchmark.

---

# 35. Benchmark Reproducibility

Synthetic data must be generated from code with a deterministic seed.

Example:

```text
seed = 20260910
```

A clean benchmark must therefore be reproducible from scratch.

Do not manually maintain thousands of synthetic rows.

---

# 36. Assessment Output

Running the v0.1 assessment must produce at minimum:

```text
assessment.json
findings.json
scorecard.json
report.md
```

Optional:

```text
report.html
report.pdf
```

PDF is required for the final public sample report but does not need to be the primary internal format.

---

# 37. Executive Report Structure

The final sample report should be approximately 8–12 pages.

Required structure:

## Page 1 — Cover

```text
Northstar Distribution
Data Janitor Assessment

Synthetic Demonstration
```

## Page 2 — Executive Summary

Answer:

- overall condition;
- biggest risks;
- AI readiness;
- most important next actions.

## Page 3 — Data Health Score

Show:

- overall score;
- six dimension scores;
- evidence coverage.

## Page 4 — Top Risks

Maximum approximately five headline findings.

## Pages 5–7 — Findings by Dimension

Summarized findings with evidence.

## Page 8 — AI Readiness

Explain:

- status;
- blockers;
- implications.

## Page 9 — Quick Wins

Problems that provide high value relative to remediation effort.

## Page 10 — 30/60/90-Day Remediation

Prioritized sequence.

## Appendix

Technical evidence and check results.

---

# 38. Report Writing Principles

The report must prefer:

> Approximately 5% of customer records appear duplicated, which can distort customer-level reporting and segmentation.

over:

> Uniqueness ratio = 0.9512.

Technical evidence should remain available in the appendix.

Executive findings must explain:

```text
What happened?
How do we know?
Why does it matter?
How serious is it?
What should happen next?
```

---

# 39. Remediation Roadmap

Recommendations should be grouped into:

```text
0–30 days
31–60 days
61–90 days
Longer term
```

The roadmap is directional.

v0.1 is not required to perform the remediation.

---

# 40. Public Proof Package

The public package must demonstrate substance without pretending the synthetic engagement is a real client.

Required public assets:

```text
README
methodology overview
benchmark overview
sample findings
sample report
synthetic-data disclosure
```

Recommended landing-page sections:

```text
What Data Janitor finds

How the assessment works

Example findings

Sample scorecard

Sample report

Who it is for

What it is not

Contact / request assessment
```

---

# 41. Public Positioning

Recommended primary message:

> Find the data problems that can make your analytics and AI unreliable before they reach production.

Supporting proposition:

> Data Janitor evaluates data quality, metric consistency, metadata, privacy hygiene, ownership, and reliability, then turns the evidence into a prioritized remediation plan.

Avoid claims such as:

- “guarantees AI success”;
- “certifies your data”;
- “ensures PDP compliance”;
- “industry-standard score”;
- “AI-powered autonomous data governance.”

---

# 42. CDMP Positioning

CDMP may be used as supporting professional credibility.

It must not imply that:

- Data Janitor is an official DAMA product;
- the scoring model is DAMA-certified;
- the assessment constitutes CDMP certification;
- DAMA endorses the methodology.

Data Janitor should stand on its own evidence and methodology.

---

# 43. Proposed Repository Structure

```text
data-janitor-assessment/
│
├── README.md
├── SPEC.md
│
├── methodology/
│   ├── overview.md
│   ├── scoring.md
│   ├── severity.md
│   └── checks/
│
├── benchmark/
│   ├── generate.py
│   ├── config/
│   ├── data/
│   └── ground_truth/
│
├── runner/
│   ├── profiling/
│   ├── checks/
│   ├── scoring/
│   └── reporting/
│
├── assessment/
│   └── northstar/
│       ├── assessment.json
│       ├── findings.json
│       └── scorecard.json
│
├── report/
│   ├── templates/
│   └── samples/
│
├── tests/
│
└── public/
    └── landing-page/
```

---

# 44. Minimal CLI / Execution Interface

A sophisticated CLI is unnecessary.

The desired conceptual interface is:

```text
data-janitor assess <dataset> <assessment-config>
```

Example:

```text
data-janitor assess benchmark/northstar.duckdb config/northstar.yaml
```

Output:

```text
Assessment complete

Overall Data Health: 58/100
AI Readiness: NOT READY

Critical: 3
High: 8
Medium: 11
Low: 6

Output:
assessment/northstar/
```

Exact CLI syntax may change during implementation.

---

# 45. Human Evidence Input

Some checks cannot be inferred from database contents.

v0.1 therefore permits an assessment configuration file.

Example:

```yaml
datasets:
  orders:
    business_owner: null
    technical_owner: data-team
    criticality: tier_1
    expected_freshness: daily

metrics:
  revenue:
    business_owner: finance
    authoritative_source: null

privacy:
  retention_policy_exists: unknown
```

Manual evidence must be clearly distinguishable from automatically observed evidence.

---

# 46. Deterministic vs AI-Assisted Results

Deterministic results include:

- duplicate count;
- null rate;
- referential-integrity violations;
- freshness;
- reconciliation differences.

These should never depend on LLM interpretation.

AI may optionally assist with:

- explaining findings;
- grouping related findings;
- suggesting draft remediation language;
- translating technical evidence for executives.

AI-generated text must not alter underlying evidence.

---

# 47. Safety and Data Handling

v0.1 must:

- operate read-only;
- default to local processing;
- avoid transmitting raw data externally;
- redact sample PII from public reports;
- clearly distinguish synthetic PII from real PII;
- never expose secrets or connection credentials in generated reports.

---

# 48. Quality Assurance

The benchmark functions as the initial test suite.

At minimum, QA must verify:

### Detection

Known injected defects produce appropriate findings.

### Non-detection

Clean control cases do not produce obviously false critical findings.

### Scoring

The same input produces the same score.

### Report consistency

The report score and findings match the structured assessment output.

### Reproducibility

Regenerating the benchmark using the same seed produces materially identical results.

---

# 49. Definition of Done

Data Janitor Assessment v0.1 is complete only when all of the following are true.

### Methodology

- six dimensions are documented;
- all 42 checks are defined;
- check modes are identified;
- scoring is implemented;
- severity logic is implemented;
- evidence coverage is implemented;
- AI readiness rules are documented.

### Benchmark

- synthetic company exists;
- synthetic dataset is generated programmatically;
- all six dimensions contain intentional defects;
- ground-truth defects are documented separately;
- benchmark can be regenerated deterministically.

### Assessment

- benchmark can be assessed without manually creating findings;
- automated checks run automatically;
- manual/hybrid checks accept structured evidence;
- normalized `findings.json` is generated;
- scorecard is generated;
- output is reproducible.

### Report

- complete sample assessment exists;
- report numbers match structured outputs;
- top findings contain evidence and business impact;
- remediation roadmap exists;
- synthetic-data disclosure is prominent.

### Public Proof

- repository can be publicly viewed;
- methodology overview exists;
- benchmark explanation exists;
- sample findings are available;
- sample report is available;
- no employer IP or confidential material is present.

---

# 50. Final Acceptance Test

The strongest v0.1 acceptance test is:

> Replace Northstar with a second unfamiliar synthetic dataset.

Without modifying the core assessment methodology:

1. profile the new data;
2. run applicable automated checks;
3. provide required manual evidence;
4. calculate scores;
5. generate findings;
6. generate an assessment report with the same structure.

If Data Janitor requires hardcoded Northstar-specific logic to produce a meaningful assessment, v0.1 has failed.

---

# 51. Explicitly Deferred to v0.2+

Not part of v0.1:

```text
Live production DB connectors
BigQuery connector
Snowflake connector
Web dashboard
Authentication
Multi-tenancy
User management
Billing
Scheduled scanning
Continuous monitoring
Slack notifications
Email notifications
Automated remediation
Data catalog UI
Column-level lineage
Access-control enforcement
Enterprise SSO
Customer portal
Benchmark against external companies
AI agents
```

These require evidence from real assessments before prioritization.

---

# 52. v0.1 Success Criterion

The success criterion is not:

> “We built a data tool.”

It is:

> A technical or data leader can inspect the public demonstration and understand what Data Janitor finds, why those findings matter, how the assessment reaches its conclusions, and what they would receive from an engagement.

And:

> The same methodology can produce a credible assessment on data it was not specifically designed around.

That is the product proof required before attempting to sell the assessment or build a larger software platform.