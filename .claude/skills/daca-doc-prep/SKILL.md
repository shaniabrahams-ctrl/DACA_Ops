---
name: daca-doc-prep
description: Pre-fill Rho/Webster springing DACA Word documents for a given borrower entity. Cross-checks all four authoritative sources (Gmail, Jira CSHELP ticket, Typeform Drive PDFs, DACA Summary tracker) before touching any document. Produces a pre-filled DOCX with [PENDING] markers for fields that require human input, and a gap report listing every outstanding item. Never sends DocuSign or uploads to Drive without explicit DRI approval.
---

# DACA Document Pre-Fill

You are preparing a pre-filled Rho/Webster Springing DACA agreement for one borrower entity. The output is a Word document with all known fields filled and `[PENDING: ...]` markers for anything still outstanding. **Never issue DocuSign, send to Webster, or overwrite existing files without explicit DRI approval.**

## Four-source data collection (mandatory — do not skip any source)

Run all four lookups before filling a single field. Cross-check them against each other and flag conflicts.

### 1. Gmail — `daca@rho.co` thread
Search: `to:daca@rho.co OR subject:DACA <borrower name>`
Capture:
- Initial inquiry date and original email chain
- Lender name as stated by the borrower (may differ slightly from Typeform)
- Any redline or acceptance emails (look for "accept," "confirm," "Webster")
- Signer names mentioned by the borrower (e.g., "Joseph Sciascia as sole signer")
- Lender counsel/rep CC'd on emails → their name, title, email

### 2. Jira CSHELP ticket
Search JQL: `text ~ "<borrower name>" AND project = CSHELP ORDER BY created DESC`
Cloud ID: `f87c0a5b-9b38-4613-b55d-cbddfc81601c`
Capture:
- Official lender name (Jira description is Shani's verified version)
- Business IDs (BIDs) for each borrower entity
- Compliance package status (who assembled, date)
- Signer compliance notes (is signer an account owner? UBO? requires board resolution?)
- Any comment notes about entity type mismatches

### 3. Typeform — DACA Application Form PDFs (primary source for lender address + contact)
**Known tool limitation:** `read_file_content` on spreadsheet ID `1Oog92OTZ5w4Lss-CSVJ-jos8d4Or3K8qu6EQe0EuvtE` truncates at ~4/2/2026. Recent submissions (submitted after ~April 2026) will NOT appear in that tool's output.

**Workaround — always use this instead:**
Search Drive: `fullText contains '<borrower name>'` — the system auto-generates DACA Application PDFs for each Typeform submission and stores them in the case folder. Read those PDFs directly.

Folder naming convention: `YYYY-MM-DD - <Borrower Entity> - <Lender Entity>` under the DACA Cases parent folder.

Each PDF contains:
- Lender legal entity name (as borrower entered it — cross-check against Jira)
- **Lender business address** ← often only available here
- Lender rep name, phone, email (Grant Sweitzer / whoever)
- Borrower entity name, address, contact
- Number of deposit accounts (single vs. multiple)
- Transfer method (ACH vs Wire)
- Submission timestamp

### 4. DACA Summary tracker
Sheet ID: `140z-O_ZoRyY97w4W5hBYBsUylQPJysj8rVXbzRJzRls`
Tab: WebsterReport (gid=1544404420)
Capture:
- Confirmed BIDs (authoritative)
- Lender name column (may be blank — flag if so)
- Account numbers (if populated — often blank until DocuSign is complete)
- Case status column

## Cross-check rules

| Conflict | Resolution |
|---|---|
| Lender name differs between Typeform PDF and Jira | Use Jira version (Shani-verified); flag discrepancy |
| Entity type not in any source | Leave as `[PENDING: ENTITY TYPE — verify from Middesk]` |
| Account numbers missing from tracker | Leave as `[PENDING: ACCOUNT NUMBER(S) — pull from Rho dashboard BID XXXXX]` |
| Multiple lender entities (e.g., 3 Soryn funds) | List all in opening sentence; in sig block use "Entity A; Entity B; and Entity C, each a [type]" |
| Signer not an account owner on the entity | Flag for compliance — do not proceed until Jira compliance comment confirms authorization |

## Template

**Current approved template:** Webster Bank redline revisions v4_4  
Drive folder: `1OdKr5BVGkAME64_nEm4nkYuVxHjzUc2-`  
SHA-256 fingerprint (as of 2026-06-10): `eff162447dd60f24840692407bc965d2ba71ff788d767f84e407ca0c2a93869f`  
Script: `src/operations/prefill_daca.py` (run with entity name as argument)

Always verify the template hash before use. If the hash differs, stop and notify the DRI — Webster may have issued a new version.

## Placeholder map

| Placeholder in template | Source | Notes |
|---|---|---|
| `[  ]` (2 spaces) in opening | Execution date — month | Set at DocuSign send time |
| `20[ ]` in opening | Execution date — year | Set at DocuSign send time |
| First `[   ]` (3 spaces) in opening | Debtor legal entity name | From Typeform PDF / Jira |
| Second `[   ]` (3 spaces) in opening | Secured Party legal entity name | From Jira (authoritative) |
| `[\t], a [\t]` — Debtor sig block | Entity name + type | Name from Typeform; type from Middesk |
| `[\t], a [\t]` — Secured Party sig block | SP name + type | Jira name; type from formation docs |
| `[list by account number]` | Schedule A accounts | Rho dashboard — BID lookup |
| `[LETTERHEAD OF THE SECURED PARTY]` | SP name (all exhibits) | Jira lender name |
| `[DATE]` | Execution date (exhibits) | Set at DocuSign send time |
| `[list account numbers]` | Account numbers (exhibits) | Rho dashboard |
| `[Debtor]` | Debtor name (exhibit body) | Typeform / Jira |
| `[NAME OF SECURED PARTY]` | SP name (exhibit sig block) | Jira lender name |
| `[Name:]` | SP signer name | Typeform PDF lender contact field |
| `[Title:]` | SP signer title | **Obtain from borrower or SP directly — not in Typeform** |
| `[NAME OF DEBTOR]` | Debtor name (cc line) | Typeform / Jira |

The main signature page (Debtor block) fields — `By: Name: Title: Address: Attention:` — are **not bracketed** in the template. They are free-form lines filled at execution. Capture the values in the gap report but do not attempt XML replacement for those lines.

## Gap report format

After running pre-fill, produce:

```
# DACA Pre-Fill Gap Report — <entity name> — <date>
Sources checked: Gmail ✓ | Jira CSHELP-XXXX ✓ | Typeform PDF ✓ | DACA Summary ✓

## Filled fields
- Debtor: <value>
- Secured Party: <value>
- Lender address: <value>
- SP signer name: <value>
[...]

## [PENDING] items — required before DocuSign
1. Execution date — set when DocuSign envelope is created
2. Debtor entity type (e.g., "Delaware LLC") — verify from Middesk report in compliance package
3. SP entity types — verify from Soryn formation documents
4. Joseph Sciascia's title — requested via email <date>
5. Grant Sweitzer's title — ask Joseph to provide, or contact Grant directly at grant@sorynipcap.com
6. Account numbers — pull from Rho dashboard: BID <XXXXX>

## Blocker flags
- <any compliance/signer authorization issues>
```

## Anonos case reference (2026-06-15)

Completed case — use as reference for future multi-entity, multi-fund cases.

| Field | Anonos Innovations LLC | Anonos Technologies LLC |
|---|---|---|
| BID | 49596 | 50258 |
| Jira | CSHELP-8871 | CSHELP-8871 |
| Debtor address | 7950 Legacy Drive, Suite 400, Plano, TX 75024 | 1603 Capitol Ave Ste 415-936874, Cheyenne, WY 82001 |
| Secured Party | Soryn IP Fund II, L.P.; Soryn IP Fund II Evergreen, L.P.; Soryn IP Parallel Fund II, L.P. | ← same |
| SP address | 45 Essex St., Suite 201, Millburn, NJ 07041 | ← same |
| SP rep | Grant Sweitzer · (717) 330-2004 · grant@sorynipcap.com | ← same |
| Signer (Debtor) | Joseph Sciascia (account owner on both) | ← same |
| Accounts | 3 checking | 1 checking |
| Transfer | ACH | ACH |
| Template used | WB redline revisions v4_4 | ← same |
| Pre-filled file | `docs/prefilled_dacas/Rho_Springing_DACA_Anonos_Innovations_LLC_PREFILL.docx` | `docs/prefilled_dacas/Rho_Springing_DACA_Anonos_Technologies_LLC_PREFILL.docx` |
| Drive case folder | `1MkzYSt4pQVdHgtkoqMK06LapPMKxu4wt` | `1Xd4y8SwYoECCsrhwWOplHRtrx4m7SWGb` |

**Pending as of 2026-06-17:** Execution date, entity types, Joseph Sciascia's title, Grant Sweitzer's title, account numbers for both entities.

## Output files

Save pre-filled DOCX to `docs/prefilled_dacas/<EntityName>_PREFILL.docx` in the repo for the audit trail. Upload to the corresponding Drive case folder only after DRI review and approval.
