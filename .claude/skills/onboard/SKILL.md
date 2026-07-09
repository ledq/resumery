---
name: onboard
description: Build the evidence bank from the user's raw career material (resumes, CVs, notes; pdf/md/txt/tex or pasted text). Ingests everything in bank/sources/ (or given paths / a paste), structures it into experience_bank.md + profile.json, interviews the user with a few high-value questions, and finishes with the evidence map. Cold-start only; it builds a bank where none exists.
---

# /onboard: build the bank from the user's raw material

Turn a pile of raw sources into the structured bank the tailoring pipeline runs on. Code
ingests, an agent structures, and you host the one conversational part: a short interview.
The user's answers and their sources are the only places facts come from.

**Voice.** Describe what is happening to the user's career material in their terms: "I've
read your three files", "your two resumes disagree on when you left Acme", "saved, your
experience bank is ready". Give a file path where the user acts on it (where their bank
lives, where to drop files). One short progress line per stage.

## 0. Cold-start guard

If `bank/experience_bank.md` already exists, stop: this command builds a bank where none
exists, and running it against a populated bank would clobber curated work. Tell the user
what exists and ask how they want to proceed (they can move the current bank aside first
if a rebuild is really intended).

## 1. Resolve the sources

`bank/sources/` is the drop box AND the permanent home: everything the user gives us lands
there, forever, unedited. From `$ARGUMENTS` (and, if empty, the conversation):

- **Path arguments** (files or a folder) → expand a folder to the supported files inside
  it (pdf, md, txt, tex), then:
  ```
  python3 ops/bank_ingest.py bank <file ...>
  ```
- **No arguments** → ingest whatever is already in the drop box:
  ```
  python3 ops/bank_ingest.py bank
  ```
  Exit 4 with nothing ingested → the box is empty: tell the user their options (drop
  files into `bank/sources/` and rerun, give paths, or paste their resume text right here).
- **Pasted text** (in the argument or earlier in this conversation) → Write it VERBATIM to
  `bank/sources/pasted-<YYYY-MM-DD>.md` (one copy, change nothing), then run the
  no-arguments form.

Invite more than one source: old resume versions, a CV, notes; the union holds more true
material than any single file, and this is the moment to collect it.

Then read `bank/.ingest/manifest.json` and act on per-source status: `low_yield`,
`not_text`, or `extract_failed` means that source is unusable as text; name the file,
say what happened, and offer the paste route for it. Proceed when at least one source is
usable.

## 2. Structure: spawn the extract agent

Spawn the `bank-extract` agent (Agent tool, `subagent_type: "bank-extract"`) with a prompt
giving the concrete paths: the bank directory (`bank/`), the manifest
(`bank/.ingest/manifest.json`), and the format contract (`spec/bank_format.md`). It writes
`bank/experience_bank.md`, `bank/profile.json`, and `bank/.ingest/gaps.md`, and returns a
one-line summary. Relay that summary. Then log the operation:

```
## [YYYY-MM-DD] extract | <roles> roles, <units> units, <agenda size> gaps
```

appended to `bank/log.md`.

## 3. The interview: interactive, every question skippable

Read `bank/.ingest/gaps.md`. Select what to ask: **every Tier-A item** (record blockers),
then Tier B, C, D in order until the total reaches **8**; drop the rest. Lead with one
plain sentence of what you found and why a few questions are worth their time (e.g. "Your
resumes are in. A few things only you can answer would make the result stronger; skip
anything freely.").

Ask via the **AskUserQuestion tool**, in batches of up to 4 questions per call, Tier-A
first. The lead-in message explains the mechanics once: answers are typed into the Other
field; the listed choices are ways to skip, so each question's text is the question alone.
How to build each question:

- **A conflict between the user's own sources** (two dates, two titles): the options ARE
  the conflicting values, each labeled with where it came from ("August 2019 (your 2022
  resume)"). The user clicks the right one, or types the real answer under Other.
- **A public-record fact** (an institution's location, a credential's issuing body):
  research it (model knowledge or a quick web search) and offer the candidates as
  options to confirm, each labeled with what it refers to ("San Marcos, CA (Cal State
  San Marcos)"). Offer candidates only when confident; otherwise ask openly. The recorded
  fact's source is the user's confirmation, never the research itself, which is also why
  ambiguity (two campuses with the name) is presented as options, not resolved silently.
- **Every personal question** (a scale, an outcome, a decision, a date of their own
  employment): the answer arrives through the built-in Other free-text field. The two
  listed options are the two ways to skip, "Skip: no such number/detail exists" and
  "Skip for now: could dig it up later", because they mean different things for the
  bank (a dead end vs. a note to revisit). Personal facts never carry suggested values:
  a proposed number, outcome, or tool name in an option is putting words in the user's
  mouth.

Rules for the answers:
- The user's answer is testimony: fold it in **verbatim**, their numbers, their words.
  An answer that hedges ("maybe 30 or so services") is recorded with its hedge.
- A record-layer answer (a date, a title, a location) updates BOTH `bank/profile.json`
  and the matching header line in `bank/experience_bank.md`; the two must round-trip.
- A narrative answer (scale, outcome, decision reasoning) is a targeted Edit to the unit
  the agenda item names: fill its thin field (`Scale`, `Results`, a new
  `Design contributions` entry). Everything else in the unit stays byte-for-byte.
- A skipped question stays a gap: leave the unit thin and the profile field null. Mark
  each item in `gaps.md` as `answered`, `skipped` (no such detail exists), or `deferred`
  (worth revisiting) so the file records what remains and why.
- One follow-up round is fine if an answer opens something clearly valuable; past that,
  stop; the bank grows later, this is not an interrogation.

Then log it: `## [YYYY-MM-DD] interview | <n> answered, <m> skipped` appended to
`bank/log.md`.

## 4. Application defaults: one optional offer

If the interview left `profile.json` without an `application` block (the sources may have
volunteered one), make ONE offer: saving application-form defaults (work authorization /
sponsorship, salary expectation, notice period, relocation, remote/hybrid/onsite
preference) means application forms never have to re-ask. One AskUserQuestion batch at
most: closed items (sponsorship, work preference) as options, free-text items via Other,
recorded verbatim into the `application` block per `spec/bank_format.md`. Decline = move
on; ask nothing item-by-item.

## 5. Integrity check

Run `python3 ops/bank_lint.py bank`. An ERROR is yours to fix before moving on: after a
fold it is usually a header line that drifted from `profile.json`; correct the file and run
the check again until no errors remain. Warnings are known gaps, already the user's choice
(a skipped date, a unit with no stack): carry them into the closing summary in plain terms
rather than fixing anything.

## 6. Index and close

Invoke the `bank-map` skill to build `bank/evidence_map.md` from the new bank. Then close
with: where everything lives (`bank/experience_bank.md`, `bank/profile.json`, the sources
in `bank/sources/`), what stayed thin (the `skipped` items in `bank/.ingest/gaps.md`, as
things worth adding when the user has the numbers), and that `/tailor <posting>` is now
ready to run.
