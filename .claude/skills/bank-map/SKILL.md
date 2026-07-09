---
name: bank-map
description: Regenerate bank/evidence_map.md, the drafter's derived index of the experience bank. Run after any edit to bank/experience_bank.md (new role, new contribution, updated facts). Reads the full bank, rebuilds the map from scratch.
---

# /bank-map: regenerate the evidence map

`bank/evidence_map.md` is a **derived index** of `bank/experience_bank.md`, read by the
draft stage to turn its JD-coverage pass into a lookup instead of a per-run re-derivation.
It is never a source of truth: every resume claim traces to the bank, and on any
disagreement the map is stale and the bank wins. Regenerate it whole: read the entire
bank fresh and rewrite the file; do not patch the old map.

## Structure (three sections, in this order)

1. **Requirement lookup**: what JDs ask → strongest bank evidence, grouped under theme
   headings (platform/backend, full-stack/frontend, data engineering, cloud/DevOps,
   databases/performance, ML/AI, systems/embedded, collaboration/communication; adjust
   themes to what the bank actually contains). Each line: the requirement as JDs phrase
   it → the evidence, tagged with `[role_id]`, plus the headline facts and a production/
   deployed marker where true.
2. **Angle inventory**: one entry per bank unit (each contribution and project). Header
   carries `[role_id]`, ownership (sole/partial), and status (production, POC, shipped,
   competition). Body lists the *distinct honest facings* the unit supports (e.g. a
   config platform may face schema design, API design, distributed systems, and IaC),
   each angle with the exact facts (numbers, tools, tradeoffs, outcomes) behind it.
3. **Absences and standing adjacency candidates**: bank-wide absence facts (languages,
   clouds, platforms, role types the bank does NOT evidence), verified by scanning the
   whole bank, so the drafter can settle gap verdicts without a full re-scan; then the
   nearest-honest-evidence candidates for requirements that recur in postings, marked
   explicitly as per-JD decisions.

## Rules

- **Facts, never prose.** Telegraphic fragments only; no sentence that could be lifted
  onto a resume. If an entry reads like a finished bullet, break it back into facts.
- **Numbers verbatim from the bank.** Metrics, costs, scale, dates: copy exactly; never
  round further or extrapolate.
- **Every entry keyed.** `[role_id]` on everything, so the drafter maps evidence to
  resume structure without re-reading headers.
- **Angles must be honest facings, not aspirations.** An angle exists only if the bank's
  facts under it would survive the evaluator's grounding check on their own.
- **Absence claims are claims.** State an absence only after checking the entire bank,
  including the projects and skills sections.
- **Never launder placeholders.** Bracketed TODOs or unfilled fields in the bank are not
  facts; where a unit has them, note the boundary ("do not claim beyond the above").
- **Stamp it.** Open the file with the generation date, the regeneration command, and
  the derived-not-source contract.

When done, confirm the map's unit count matches the bank's (every contribution and
project has exactly one angle-inventory entry) and stop.
