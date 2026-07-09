---
name: tailor
description: Tailor the resume to one job posting. Give it a URL, paste the posting (or refer to one pasted earlier in this chat), or point at a saved application folder; it resolves the JD and runs the tailor-pipeline workflow end to end.
---

# /tailor: front door for the tailoring pipeline

Resolve WHICH JD the user means, confirm it really is a job posting, mint the
application workspace, hand the engine the workspace, and relay the result. The file on
disk is always the canonical text: you read the JD to judge it, but the copy the
pipeline receives is the file's.

## 1. Mint the staging namespace: FIRST, once

```
mktemp -d /tmp/jd_stage.XXXXXX
```

It prints the run's namespace directory (call it `<dir>`). This is the ONLY randomness
in staging, minted once; every step below uses fixed names inside it (`<dir>/jd.txt`,
`<dir>/url`). Always a fresh `mktemp -d`: a fixed path is shared mutable state, and a
leftover from an earlier run would silently tailor the resume to a stale JD.

## 2. Fill it: every source becomes `<dir>/jd.txt`

From `$ARGUMENTS` (and, if it is empty, the conversation):

- **A URL** → fetch into the namespace deterministically:
  ```
  python3 ops/jd_fetch.py '<url>' <dir>
  ```
  Exit 0 → the posting is at `<dir>/jd.txt` (the URL lands at `<dir>/url`, where
  step 4's script reads it for identity; not your concern after this command). Exit 4 → the page is JS-rendered or
  blocked the fetch: tell the user and ask them to paste the posting text instead.
- **A saved application** (an `applications/<id>` path or id) → no staging; the folder
  already holds the posting. Use `applications/<id>/jd.txt` as the JD path in the steps
  below. (Step 4's identity check will match and reuse the folder; this is how a saved
  or previously tailored posting is re-tailored.)
- **A path to a JD file the user already has** → copy it in:
  `cp '<their file>' <dir>/jd.txt`.
- **Raw posting text** (in the argument, or pasted earlier in this conversation) →
  use the Write tool to put the posting at `<dir>/jd.txt`, VERBATIM: one copy,
  change nothing, drop nothing.
- **Ambiguous** (several JDs in this chat, or none anywhere) → ask the user which
  posting they mean, or for the posting itself. Do not guess.

## 3. Confirm it is a posting; extract company and role

Read the staged `jd.txt` (whichever source filled it). If it is plainly not a job
posting (a login or block page, a cookie-consent wall, a search-results index, an
"expired posting" notice), STOP before any workspace exists: tell the user what came
back and ask for the posting text. A garbage jd.txt does not fail the pipeline; it
produces a confidently tailored resume against nonsense, caught only by the human.

From the same read, note the `company` and `role_title` the posting states, for step 4.
Honest absence: when the posting does not state one, you have nothing to pass on.

## 4. Mint the workspace (code owns this)

Run `ops/new_workspace.py`, pointing it at the staged JD:

```
python3 ops/new_workspace.py --jd-file '<jd path>' --company "<company>" --role "<role>"
```

Omit `--company`/`--role` when the JD does not state them. Double-quote the values
(names like O'Reilly carry apostrophes). The script decides create vs. reuse and names
the folder; its **last stdout line is the workspace path**. Use that path exactly as
printed; never retype it or construct one yourself. Exit 2 means the JD file was
unreadable or empty: tell the user and stop; no workspace exists.

The JD path always comes from THIS turn (the namespace minted in step 1, or the saved
application's `jd.txt`), never from an earlier turn's namespace (an earlier run's
namespace holds an earlier run's posting).

## 5. Invoke the engine

Call the Workflow tool with `name: "tailor-pipeline"` and:

```
args: { "workspace": "applications/<id>" }
```

using the path step 4 printed. `args` must be an actual JSON OBJECT in the tool call,
not a JSON-encoded string (a stringified object reaches the script as one string).
Never modify the workspace's files yourself; the engine owns them from here.

## 6. Relay the result

Report the workflow's closing message to the user with the exact workspace folder and
the `Resume_*.pdf` path. Phrase the flagged gaps as advice for the human (what to be ready to
speak to), not as pipeline telemetry. If the run stopped early, relay the reason and the
suggested retry (re-running with the same JD reuses the workspace cleanly).
