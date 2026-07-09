#!/usr/bin/env bash
# check.sh: deterministic quality gate, fired as a PostToolUse hook after a workspace
# write; also runs directly for testing (`bash check.sh applications/<id>`).
#
# One firing, one combined verdict. resume.json -> render.py -> three gates:
#   format    compile -> page count -> page fill (serial: each needs the previous)
#   lints     render.py's lint_flags.md
#   keywords  ops/keyword_check.py
# All failures come back in one exit-2 message and the writer rewrites (warm
# self-fix). Each gate kind has its own retry counter: at GATE_MAX_ATTEMPTS it is
# capped, stops blocking, ships flagged (format via .build/format_escape.md), and
# stays capped until it passes. Everything still failing capped -> exit 0, move on.
#
# render.py owns character normalization; this script only builds and measures.

set -uo pipefail

MAX_PAGES="${RESUME_MAX_PAGES:-1}"
MIN_FILL="${RESUME_MIN_FILL:-85}"                  # min % of the last page carrying ink
GATE_MAX_ATTEMPTS="${GATE_MAX_ATTEMPTS:-3}"

# --- resolve context: which file was written, in which workspace -------------
# Hook stdin carries {"tool_input":{"file_path":...}}. Workspace = CLI arg (manual
# run), else the edited file's folder with any trailing /.run stripped.
WS_ARG="${1:-}"
INPUT="$(cat 2>/dev/null || true)"
CANDIDATE=""
if [ -n "$INPUT" ]; then
  CANDIDATE="$(printf '%s' "$INPUT" \
    | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
    | head -n1)"
fi

if [ -n "$WS_ARG" ]; then
  WS="$WS_ARG"
elif [ -n "$CANDIDATE" ]; then
  WS="$(dirname "$CANDIDATE")"
  case "$WS" in */.run) WS="${WS%/.run}" ;; esac
else
  echo "check.sh: no workspace argument and no hook input; nothing to check." >&2
  exit 0
fi
BUILD="$WS/.build"          # LaTeX aux/log/pdf, counters, lint + escape markers
TEX_DEFAULT="$WS/.run/resume.tex"

# --- workspace marker gate ----------------------------------------------------
# jd.txt (written only by ops/new_workspace.py) marks a real workspace; bounce run
# files aimed anywhere else before Write's auto-mkdir forks a phantom folder.
if [ -n "$CANDIDATE" ]; then
  case "$(basename "$CANDIDATE")" in
    resume.json|parsed_jd.json|review_notes.md|review_reverify.md|fix_notes.md|gaps.md|run.json)
      if [ ! -f "$WS/jd.txt" ]; then
        printf 'BLOCK: %s is not an initialized workspace (no jd.txt marker). Write run files only to the exact workspace path you were given in your instructions.\n' "$WS" >&2
        exit 2
      fi ;;
  esac
fi

# --- perf log ------------------------------------------------------------------
# One line per firing; .build/ resets per run, so the log is per-run automatically.
if [ -n "$CANDIDATE" ] && [ -f "$WS/jd.txt" ]; then
  mkdir -p "$BUILD"
  printf '%s %s\n' "$(date +%s.%N)" "$(basename "$CANDIDATE")" >> "$BUILD/perf.log"
fi

# --- retry counters -------------------------------------------------------------
# One counter per gate kind, counting consecutive failing writes; a pass resets it.
# A manual run means a human intervened: reset everything, count nothing.
GATE_FMT="$BUILD/.gate_attempts_fmt"
GATE_LINT="$BUILD/.gate_attempts_lint"
GATE_KW="$BUILD/.gate_attempts_kw"
FORMAT_ESCAPE="$BUILD/format_escape.md"   # durable marker: format gate gave up, defect ships
IS_HOOK=0
[ -n "$INPUT" ] && IS_HOOK=1
[ "$IS_HOOK" -eq 0 ] && rm -f "$GATE_FMT" "$GATE_LINT" "$GATE_KW"

# --- output helpers --------------------------------------------------------------

# The hook runner drops plain stdout on exit 0; agent-facing messages ride this envelope.
hook_json() {  # $1 = message for the agent
  printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"%s"}}\n' "${1//\"/\\\"}"
}

# Durable "format gate gave up" flag, read by present-log and the finalize sweep;
# rewritten on every capped write so it describes the defect that actually ships.
record_format_escape() {  # $1 = the current format issue text
  printf 'FORMAT ESCAPE: warm self-fix hit the retry cap (%s attempts) with the format gate still failing (resume not compiling, over one page, or under-filled).\n\n%s\n' "$GATE_MAX_ATTEMPTS" "$1" > "$FORMAT_ESCAPE"
}

# Fully clean: reset all counters, clear the escape marker, tell the writer.
report_success() {  # $1 = success message
  rm -f "$GATE_FMT" "$GATE_LINT" "$GATE_KW" "$FORMAT_ESCAPE"
  if [ "$IS_HOOK" -eq 1 ]; then
    hook_json "$1"
  else
    printf '%s\n' "$1"
  fi
  exit 0
}

# Invalid resume.json: nothing downstream is measurable, so exit immediately. Shares
# the format counter but resets it at the cap; a page failure after the JSON recovers
# deserves a fresh blocking budget, not a silent pre-capped pass.
fail_render() {  # $1 = render.py output
  if [ "$IS_HOOK" -eq 1 ]; then
    local n
    n=$(cat "$GATE_FMT" 2>/dev/null || echo 0)
    n=$((n + 1))
    printf '%s' "$n" > "$GATE_FMT"
    if [ "$n" -ge "$GATE_MAX_ATTEMPTS" ]; then
      printf '%s\n' "$1" >&2
      record_format_escape "$1"
      rm -f "$GATE_FMT"
      hook_json "Retry limit reached ($GATE_MAX_ATTEMPTS attempts) on: format. These are flagged for review; do NOT rewrite resume.json to address them. Continue with the rest of your task."
      exit 0
    fi
  fi
  printf '%s\n' "$1" >&2
  exit 2
}

# --- measurement helpers -----------------------------------------------------
page_count() {  # $1 = pdf; prints the page count, or nothing if no tool can read it
  local pdf="$1" n=""
  command -v pdfinfo >/dev/null 2>&1 \
    && n="$(pdfinfo "$pdf" 2>/dev/null | awk '/^Pages:/ {print $2}')"
  [ -z "$n" ] && command -v pdftk >/dev/null 2>&1 \
    && n="$(pdftk "$pdf" dump_data 2>/dev/null | awk '/NumberOfPages/ {print $2}')"
  printf '%s' "$n"
}

page_fill() {  # $1 = pdf; prints the LAST page's ink fill as a whole %, or nothing
  command -v pdftotext >/dev/null 2>&1 || return 0
  pdftotext -bbox "$1" - 2>/dev/null | awk '
    /<page / { max = 0; h = 0
               if (match($0, /height="[0-9.]+"/)) h = substr($0, RSTART+8, RLENGTH-9) + 0 }
    { line = $0
      while (match(line, /yMax="[0-9.]+"/)) {
        y = substr(line, RSTART+6, RLENGTH-7) + 0
        if (y > max) max = y
        line = substr(line, RSTART+RLENGTH)
      } }
    END { if (h > 0) printf "%d", 100 * max / h }'
}

# --- decide what to compile ---------------------------------------------------
# resume.json is rendered to .tex first; render.py validates it and exits non-zero on
# bad input.
TEX=""
case "$CANDIDATE" in
  *resume.json)
    mkdir -p "$BUILD"
    RENDER_OUT="$(python3 ops/render.py "$WS" 2>&1)"
    if [ $? -ne 0 ]; then
      fail_render "$RENDER_OUT"
    fi
    TEX="$TEX_DEFAULT" ;;
  *.tex)
    TEX="$CANDIDATE" ;;
esac

# Any other edit (review_notes.md, profile.json, gaps.md, a .py, ...) drives no compile.
if [ -z "$TEX" ]; then
  if [ -n "$INPUT" ] && printf '%s' "$INPUT" | grep -q '"file_path"'; then
    echo "check.sh: edited file does not drive a compile; nothing to do." >&2
    exit 0
  fi
  TEX="$TEX_DEFAULT"
fi
[ ! -f "$TEX" ] && TEX="$TEX_DEFAULT"

if [ ! -f "$TEX" ]; then
  echo "check.sh: no .tex file found at '$TEX'; nothing to check." >&2
  exit 0
fi

# --- gate 1: format (compile -> page count -> page fill) -----------------------
# Compiles into .build/ (the finalize sweep lifts the PDF later). At most one format
# issue is reported: no PDF -> nothing to measure, over a page -> cut before fill
# means anything, page count OK -> judge fill (the writer cannot see the rendered
# page; this measurement is its only signal).
JOB="$(basename "$TEX" .tex)"

if ! command -v pdflatex >/dev/null 2>&1; then
  echo "check.sh: pdflatex not installed; skipping compile/page check." >&2
  exit 0
fi

mkdir -p "$BUILD"
LOG="$(pdflatex -interaction=nonstopmode -halt-on-error -output-directory "$BUILD" "$TEX" 2>&1)"
RC=$?

FMT_ISSUE=""
PAGES=""
FILL=""
if [ $RC -ne 0 ] || [ ! -f "$BUILD/$JOB.pdf" ]; then
  ERR="$(printf '%s\n' "$LOG" | grep -E '^!|Error|Undefined|Runaway' | head -n 8)"
  FMT_ISSUE="$(printf 'BLOCK: LaTeX failed to compile %s. Fix the syntax and rewrite the file.\nFirst errors:\n%s' "$TEX" "$ERR")"
else
  PAGES="$(page_count "$BUILD/$JOB.pdf")"
  if [ -z "$PAGES" ]; then
    echo "check.sh: compiled OK but could not determine page count (no pdfinfo/pdftk)." >&2
  elif [ "$PAGES" -gt "$MAX_PAGES" ]; then
    FMT_ISSUE="$(printf 'BLOCK: resume compiled to %s pages; target is %s.\nCut the lowest-priority bullet (bullets are in priority order in resume.json,\nso cut the trailing bullet of the role with the most bullets), then rewrite\nresume.json. Do not expand or restructure other content.' "$PAGES" "$MAX_PAGES")"
  else
    FILL="$(page_fill "$BUILD/$JOB.pdf")"
    if [ -n "$FILL" ] && [ "$FILL" -lt "$MIN_FILL" ]; then
      FMT_ISSUE="$(printf 'BLOCK: resume fills only %s%% of the page; target is at least %s%%.\nSurface more true bank material: add a Projects section if the resume has none,\notherwise add a high-signal bullet to the most JD-relevant role. Every addition\nmust trace to the bank; never pad or fabricate. Then rewrite resume.json.' "$FILL" "$MIN_FILL")"
    fi
  fi
fi

# --- gate 2: craft lints --------------------------------------------------------
# Flagged by render.py in lint_flags.md ("- " line = flag); no PDF needed, so this is
# measured on every write regardless of format status.
LINT_ISSUE=""
if grep -q '^- ' "$BUILD/lint_flags.md" 2>/dev/null; then
  LINT_ISSUE="$(printf 'CRAFT LINTS, must fix: tighten an over-length bullet while keeping its outcome and metric; vary a repeated lead verb:\n\n%s' "$(cat "$BUILD/lint_flags.md")")"
fi

# --- gate 3: keywords -------------------------------------------------------------
# JD-keyword presence and spelling ("- " line = block; semantics in
# ops/keyword_check.py). Needs only resume.json + parsed_jd.json, so a persistent
# format failure never starves it; the report stays durable in keyword_report.md.
KW_ISSUE=""
if [ -f "$WS/.run/resume.json" ] && [ -f "$WS/.run/parsed_jd.json" ]; then
  python3 ops/keyword_check.py "$WS" > "$BUILD/keyword_report.md" 2>/dev/null || true
  if grep -q '^- ' "$BUILD/keyword_report.md" 2>/dev/null; then
    KW_ISSUE="$(printf 'KEYWORD GATE, action needed: for each "missing" line, surface that keyword honestly from the bank with a targeted Edit, or, when the bank cannot honestly back it as a resume claim, record it in gaps.md (gap or adjacency) instead. For each "spelling" line: use the JD'"'"'s spelling, or add it once alongside the current form:\n\n%s' "$(cat "$BUILD/keyword_report.md")")"
  fi
fi

# --- manual run: format decides the exit; lints/keywords are informational --------
if [ "$IS_HOOK" -eq 0 ]; then
  if [ -n "$FMT_ISSUE" ]; then
    printf '%s\n' "$FMT_ISSUE" >&2
    exit 2
  fi
  MSG="check.sh: OK: $TEX compiled to ${PAGES:-?} page(s), within target of $MAX_PAGES; page fill ${FILL:-?}%."
  [ -n "$LINT_ISSUE" ] && MSG="$MSG Craft lints present (.build/lint_flags.md)."
  [ -n "$KW_ISSUE" ] && MSG="$MSG Keyword gate has open lines (.build/keyword_report.md)."
  printf '%s\n' "$MSG"
  exit 0
fi

# --- hook verdict: arbitrate each kind, then report once ---------------------------
BLOCKING=""   # messages of kinds that still block this write
CAPPED=""     # labels of kinds at the cap and still failing (ship flagged)

# Fold one gate kind's measurement into the verdict:
#   pass            -> counter reset (format also clears its escape: flag follows defect)
#   fail under cap  -> counter +1; blocks
#   fail at cap     -> stops blocking, ships flagged; counter holds at the cap so the
#                      kind stays capped until it actually passes
arbitrate() {  # $1 = kind label, $2 = issue message ('' = pass), $3 = counter file
  if [ -z "$2" ]; then
    rm -f "$3"
    [ "$3" = "$GATE_FMT" ] && rm -f "$FORMAT_ESCAPE"
    return
  fi
  local n
  n=$(cat "$3" 2>/dev/null || echo 0)
  if [ "$n" -lt "$GATE_MAX_ATTEMPTS" ]; then
    n=$((n + 1))
    printf '%s' "$n" > "$3"
  fi
  if [ "$n" -ge "$GATE_MAX_ATTEMPTS" ]; then
    CAPPED="$CAPPED $1"
    [ "$3" = "$GATE_FMT" ] && record_format_escape "$2"
  else
    BLOCKING="$BLOCKING$2

"
  fi
}

arbitrate "format" "$FMT_ISSUE" "$GATE_FMT"
arbitrate "craft lints" "$LINT_ISSUE" "$GATE_LINT"
arbitrate "keywords" "$KW_ISSUE" "$GATE_KW"

# One combined message; capped kinds are fenced off so the writer never re-fights them.
if [ -n "$BLOCKING" ]; then
  [ -n "$CAPPED" ] && BLOCKING="$BLOCKING(Already at the retry cap and flagged for review, do NOT address:$CAPPED. Fix only the issues above.)

"
  printf '%sThen write resume.json again.\n' "$BLOCKING" >&2
  exit 2
fi

# Only capped defects remain: nothing blocks; they ship flagged for human review.
if [ -n "$CAPPED" ]; then
  hook_json "Retry limit reached ($GATE_MAX_ATTEMPTS attempts) on:$CAPPED. These are flagged for review; do NOT rewrite resume.json to address them. Continue with the rest of your task."
  exit 0
fi

report_success "CLEAN: $JOB.pdf compiled, $PAGES page(s) (target $MAX_PAGES), page fill ${FILL:-?}% (min $MIN_FILL%), no craft lints, keyword gate clear. Nothing to fix."
