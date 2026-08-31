# SourceLoop Investigate

SourceLoop Investigate is the governed active-market research layer of SourceLoop. It converts a legitimate research or procurement question into a transparent direct-source conversation and preserves the answer as evidence-linked intelligence.

It is designed for questions that passive web monitoring cannot reliably answer:

- What does a provider currently charge for a standardized scope?
- Does a business actually serve a particular geography?
- Is an employment agency charging applicants or disclosing the employer and wage?
- What legal entity and license does a contractor or lender claim?
- What capacity, availability, exclusions, and terms are current?
- Which public business contact is responsible for the question?

It is not a covert infiltration system. The runtime requires a truthful requester, discloses automated assistance, uses public or customer-authorized business channels, and routes higher-risk findings to human review.

## Product modes

| Mode | Purpose | Typical output |
|---|---|---|
| `quote_probe` | Obtain current, comparable non-binding prices and terms | Quote table and price-by-unit statistics |
| `practice_audit` | Collect a business's current public representation of a practice | Evidence-linked findings and disclosure coverage |
| `compliance_probe` | Compare public representations with registry or policy evidence | Findings, registry checks, contradictions, review queue |
| `market_census` | Map who operates where, what they provide, and current capacity | GIS/graph coverage and availability intelligence |
| `record_verification` | Confirm a public business or organization record | Corrected identity, status, and contact route |

## Installed packs

### Procurement and quoting

- `facilities_quote` — recurring commercial facility services.
- `local_services_quote` — lawn care, snow removal, cleaning, junk removal, and similar geographically constrained services.
- `bpo_quote` — BPO and outsourced operations proposals.
- `staffing_procurement` — employer-side staffing rates, capacity, screening, and conversion terms.

### Verification and market integrity

- `business_record_verification` — low-risk public business record checks.
- `contractor_license_audit` — legal identity, license, insurance, deposit, scope, and service-area representations.
- `employment_agency_audit` — applicant fees, job availability, wage, schedule, employer identity, and complaint route.
- `franchise_service_audit` — location-specific price, mandatory fees, availability, and policy treatment.
- `informal_business_verification` — public-facing business identity, service scope, price basis, and availability for under-documented providers.
- `lender_disclosure_audit` — restricted institutional research into legal identity, license, APR, finance charge, total repayment, rollover, and ACH practices.

### Civic intelligence

- `civic_intelligence` — public organization, role, service-area, meeting, and referral verification without private-person surveillance.

## Risk tiers

### Low and standard

Routine nonbinding business quotation or public-record verification. Initial messages still require approval unless a pack is explicitly configured otherwise.

### Elevated

Employment, contractor, civic, staffing, franchise, or informal-market research. These cases require a requester email and public or customer-authorized contact routes. They cannot use fabricated identities or residential mapping.

### Restricted

Institutional-only research such as alternative-lender disclosure audits. Restricted cases require explicit acknowledgements for institutional authority, legal review, research-only use, public business channels, no fake persona, no application, and no sensitive personal data.

Restricted messages state that the inquiry is not an application, purchase, contract acceptance, or request for sensitive personal information.

## Evidence model

Every external answer remains linked to its original message. Derived objects retain evidence IDs:

```text
RFC 822 message / attachment
        ↓
normalized interaction
        ↓
field coverage
        ↓
claim / quote / finding
        ↓
registry corroboration or human review
        ↓
GIS and relationship graph
```

A finding is not automatically a legal conclusion. For example, “no matching license was found in the checked registry” is recorded as a reviewable result, not as a declaration that the business is unlawful.

## Deterministic financial and pricing checks

The investigation layer performs limited, transparent arithmetic checks:

- Lender responses can produce a simple annualized cost estimate from amount disbursed, finance charge, and term. This is explicitly labeled as a comparison metric, not a legal Truth in Lending APR calculation.
- The stated amount disbursed plus finance charge is compared with stated total repayment.
- Staffing proposals can produce an implied markup from bill and worker pay rates and flag a material difference from a reported markup.
- Quote reports compute minimum, median, mean, and maximum price by currency and unit.

The original values and calculation inputs remain visible.

## Operator review

Operators can:

- inspect the exact message before approval;
- reject an initial message or clarification;
- import public/customer-authorized contact routes;
- add registry-check results and evidence references;
- mark findings corroborated, resolved, or dismissed with reviewer notes;
- export JSON or CSV reports;
- see missing critical fields by respondent;
- inspect graph relationships between contacts, messages, findings, quotes, and registry checks.

## API examples

Create a local-service quote case:

```bash
curl -sS http://localhost:8080/api/v1/cases \
  -H 'Content-Type: application/json' \
  -d @examples/local_services_quote.json
```

Create a restricted lender-disclosure research case:

```bash
curl -sS http://localhost:8080/api/v1/cases \
  -H 'Content-Type: application/json' \
  -d @examples/lender_disclosure_audit.json
```

Add a registry result:

```bash
curl -sS http://localhost:8080/api/v1/cases/CASE_ID/registry-checks \
  -H 'Content-Type: application/json' \
  -d '{
    "registry": "State contractor registry",
    "query": "Example Roofing LLC",
    "subject_id": "CONTACT_ID",
    "status": "matched",
    "identifier": "PA-123456",
    "source": "official registry URL"
  }'
```

Review a finding:

```bash
curl -sS http://localhost:8080/api/v1/cases/CASE_ID/findings/FINDING_ID/review \
  -H 'Content-Type: application/json' \
  -d '{
    "status": "corroborated",
    "reviewer": "licensed-investigator",
    "notes": "Confirmed with a second authoritative source."
  }'
```

Export a report:

```bash
curl -sS http://localhost:8080/api/v1/cases/CASE_ID/report
curl -sS http://localhost:8080/api/v1/cases/CASE_ID/report.csv -o report.csv
```

## Prohibited uses

Packs and deterministic policy rules prohibit or constrain:

- fake residents, borrowers, job seekers, customers, or property owners;
- applications, hard credit pulls, purchases, contract acceptance, deposits, or funds transfer;
- requesting Social Security numbers, bank credentials, authentication secrets, or similar sensitive data;
- contacting private individuals because of inferred political beliefs or private group membership;
- residential mapping of organizers or informal providers;
- facilitating illegal goods, services, unlicensed lending, or labor exploitation;
- publishing a legal accusation from one uncorroborated response;
- sharing one supplier's confidential quote with a competing supplier;
- continuing after an opt-out.

## Extension points

The current system accepts supplied public/business contact routes and registry results. Production packs can add scoped connectors for official licensing registries, customer CRMs, public organization directories, GIS layers, and search services. Connector output should enter the same typed contact, registry-check, evidence, and claim contracts rather than bypassing the policy ledger.
