export const meta = {
  name: 'tailor-pipeline',
  description: 'Engine behind the /tailor skill: Parse → Draft → Evaluate → one audited Fix pass, run entirely inside the application workspace (applications/<id>/; pipeline state under its .run/). Args: { workspace: string }. The skill resolves the JD (staging namespace, verbatim jd.txt), confirms it is a posting, and mints the workspace itself via ops/new_workspace.py (code owns naming + identity, create vs reuse), so the posting is already at <ws>/jd.txt when this engine starts; only the workspace path crosses the boundary, and the posting URL rides code-owned files (staging `url` -> .run/posting_url) without passing through an agent. Produces gaps.md in the workspace; present-log writes .run/run.json and a Stop-hook sweep (ops/finalize.py) derives README.md, the named Resume_*.pdf, the ledger row, and regenerates applications/index.md.',
  phases: [
    { title: 'Parse',    detail: 'write .run/parsed_jd.json from the posting (only when absent; reused applications keep theirs)' },
    { title: 'Draft',    detail: 'plan the selection; write resume.json (warm self-fix keeps format + lints clean via the hook); log gaps/adjacency to gaps.md' },
    { title: 'Evaluate', detail: 'score 9 rubric dimensions cold' },
    { title: 'Fix',      detail: 'one targeted patch pass, then a cold audit of the changed fields' },
    { title: 'Present',  detail: 'close out: complete gaps.md, write run.json; Stop-hook sweep derives README/named PDF/ledger/index' },
  ],
}

// The pipeline is linear, no loops. Whatever the one fix pass leaves unresolved ships
// honestly in gaps.md; further iteration is the human's call (/revise), not a counter's.

// ─── schemas ─────────────────────────────────────────────────────────────────

const PARSE_SCHEMA = {
  type: 'object',
  required: ['status'],
  properties: {
    status: {
      type: 'string',
      enum: ['written', 'kept', 'failed'],
      description: "'written' when parsed_jd.json was created this run, 'kept' when a " +
        "reused application already had one (left untouched), 'failed' when no valid " +
        "file could be produced.",
    },
  },
}

const EVAL_SCHEMA = {
  type: 'object',
  required: ['verdict'],
  properties: {
    verdict:            { type: 'string', enum: ['PASS', 'REVISE'] },
    grounding_failures: { type: 'number', description: 'Commission (ungrounded-claim) issues found' },
    material_count:     { type: 'number', description: 'Total MATERIAL findings' },
  },
}

const AUDIT_SCHEMA = {
  type: 'object',
  required: ['verdict'],
  properties: {
    verdict:          { type: 'string', enum: ['PASS', 'REVISE'] },
    new_fabrications: { type: 'number', description: 'Ungrounded claims introduced by the fix' },
    unresolved_count: { type: 'number', description: 'Findings still not resolved' },
  },
}

const stop = (reason, message) => {
  log(`STOP: ${reason}`)
  return { status: 'stopped', reason, message }
}

// ─── input ───────────────────────────────────────────────────────────────────
// The /tailor skill has already staged the JD, confirmed it is a posting, and minted
// the workspace via ops/new_workspace.py (deterministic code owns naming, identity,
// create vs reuse, and the jd.txt marker). Only the workspace path crosses this
// boundary; the posting is at <ws>/jd.txt. The caller is an LLM, so normalize
// instead of trusting perfect tool-call shape.

let input = args
if (typeof input === 'string') {
  const s = input.trim()
  try { input = JSON.parse(s) } catch (e) { input = { workspace: s } }
  if (input === null || typeof input !== 'object') input = { workspace: s }
}

// Bind the workspace ONCE; every later message interpolates this value, so no agent
// composes a path. The skill relays new_workspace.py's stdout into args; this shape
// check plus the jd.txt marker gate (check.sh) fence that relay on both sides.
const WS = (input && typeof input.workspace === 'string') ? input.workspace.trim() : ''
if (!/^applications\/[A-Za-z0-9._-]+$/.test(WS)) {
  return stop('no_workspace',
    'No application workspace provided. Pass { workspace: "applications/<id>" }, the ' +
    'exact path ops/new_workspace.py printed when the /tailor skill minted the ' +
    'workspace. Nothing was generated.')
}

// ─── parse: record the posting's tracking metadata ───────────────────────────
// The agent extracts the semantic fields (honest absence against the schema) and
// writes .run/parsed_jd.json only when absent; a reused application keeps its
// original parse. The file feeds the keyword gate and the tracking ledger.

// Stage models are pinned: the agent .mds say 'model: inherit', which would make cost,
// latency, and behavior vary with whichever session happened to launch /tailor.
log('→ parse')
const parsed = await agent(
  `Your workspace is \`${WS}/\`. The posting is at ${WS}/jd.txt. Record its tracking ` +
  `metadata per your instructions (write ${WS}/.run/parsed_jd.json only when absent) ` +
  `and return the status.`,
  { agentType: 'jd-parse', label: 'parse', phase: 'Parse', model: 'sonnet', schema: PARSE_SCHEMA },
)
if (!parsed || parsed.status === 'failed') {
  return stop('parse_failed',
    'The parse stage could not produce parsed_jd.json, which feeds the keyword gate ' +
    'and the tracking ledger. The workspace is intact; re-run /tailor with the same ' +
    'JD and the identity check will reuse it cleanly.')
}

// ─── draft ───────────────────────────────────────────────────────────────────
// Writes .run/resume.json and the evidence-gap half of gaps.md. Format and craft lints
// are warm self-fix INSIDE the writing stages (PostToolUse check.sh); a rare cap-hit
// escape is recorded durably in .build/format_escape.md and read by present-log.

log('→ draft')
const draftResult = await agent(
  `Your workspace is \`${WS}/\`. Concrete paths for this run: the posting is ` +
  `${WS}/jd.txt; write ${WS}/.run/resume.json; append gaps to ${WS}/gaps.md. Draft the ` +
  `tailored resume per your instructions.`,
  { agentType: 'resume-draft', label: 'draft', phase: 'Draft', model: 'sonnet' },
)
if (!draftResult) {
  return stop('draft_failed',
    'The draft stage returned no result. Re-run /tailor; the identity check reuses ' +
    'the workspace, so nothing is lost.')
}

// ─── evaluate (cold) ─────────────────────────────────────────────────────────

log('→ evaluate')
const evalResult = await agent(
  `Your workspace is \`${WS}/\`. Evaluate the tailored resume per your instructions. ` +
  `Concrete paths for this run: the resume is ${WS}/.run/resume.json; the posting is ` +
  `${WS}/jd.txt; write ${WS}/.run/review_notes.md.`,
  { agentType: 'resume-evaluate', label: 'evaluate', phase: 'Evaluate', model: 'sonnet', schema: EVAL_SCHEMA },
)

if (!evalResult) {
  return stop('evaluate_failed',
    'The evaluate stage returned no result, so there is no verdict to act on. The ' +
    'draft is intact in the workspace; re-run /tailor and the identity check reuses ' +
    'it cleanly.')
}

const firstPassGrounding = evalResult.grounding_failures || 0
let   finalVerdict       = evalResult.verdict || 'REVISE'
let   fixed              = false

// ─── fix, then audit: one pass ─────────────────────────────────────
// The fixer patches exactly what review_notes.md names; the auditor cold-checks the
// changed fields (still bank-true? each finding actually resolved?). The audit's
// verdict is final.

if (finalVerdict !== 'PASS') {
  log('→ fix')
  await agent(
    `Your workspace is \`${WS}/\`. Apply the evaluator's findings per your ` +
    `instructions. Concrete paths for this run: the findings are ` +
    `${WS}/.run/review_notes.md; the resume is ${WS}/.run/resume.json; the posting is ` +
    `${WS}/jd.txt; write ${WS}/.run/fix_notes.md; disagreements go to ${WS}/gaps.md.`,
    { agentType: 'resume-fix', label: 'fix', phase: 'Fix', model: 'sonnet' },
  )
  fixed = true

  log('→ audit')
  const audit = await agent(
    `Your workspace is \`${WS}/\`. Audit the fix per your instructions. Concrete ` +
    `paths for this run: the resume is ${WS}/.run/resume.json; the fixer's log is ` +
    `${WS}/.run/fix_notes.md; the prior findings are ${WS}/.run/review_notes.md; write ` +
    `${WS}/.run/review_reverify.md.`,
    { agentType: 'resume-reverify', label: 'audit', phase: 'Fix', model: 'sonnet', schema: AUDIT_SCHEMA },
  )
  finalVerdict = (audit && audit.verdict) || 'REVISE'
}

// ─── present + log ───────────────────────────────────────────────────────────

log('→ present + log')
const unresolved = fixed && finalVerdict !== 'PASS'
const iterations = fixed ? 1 : 0

const presentResult = await agent(
  `Your workspace is \`${WS}/\`. Concrete paths for this run: gate status at ` +
  `${WS}/.build/format_escape.md and ${WS}/.build/lint_flags.md; complete ` +
  `${WS}/gaps.md; write ${WS}/.run/run.json. Run your close-out procedure with this ` +
  `run's values:\n` +
  (unresolved
    ? `- Run-level gaps.md item, UNRESOLVED: the fix pass did not resolve every ` +
      `finding; final verdict is ${finalVerdict}. List exactly what remains ` +
      `unresolved from ${WS}/.run/review_reverify.md.\n`
    : '') +
  `- num_gaps command (run exactly): awk '/^## Evidence gaps/{f=1;next} /^## /{f=0} ` +
  `f&&/^- /{c++} END{print c+0}' ${WS}/gaps.md\n` +
  `- run.json shape (exact): {"timestamp": "<from date -u>", ` +
  `"iterations_used": ${iterations}, "final_verdict": "${finalVerdict}", ` +
  `"grounding_failures_first_pass": ${firstPassGrounding}, ` +
  `"num_gaps": <derived in your step 3>}`,
  {
    agentType: 'present-log',   // its frontmatter Stop hook runs the finalize sweep
    label:     'present-log',
    phase:     'Present',
    schema: {
      type: 'object',
      required: ['summary', 'num_gaps'],
      properties: {
        summary:  { type: 'string' },
        num_gaps: { type: 'number', description: `Evidence gaps counted in ${WS}/gaps.md` },
      },
    },
  },
)

// ─── done ────────────────────────────────────────────────────────────────────

log(`✓ done: ${WS}/ (Resume_*.pdf + gaps.md; README + index via the finalize sweep)`)

const message = ((presentResult && presentResult.summary) ||
  `Tailoring finished (verdict ${finalVerdict}, ${iterations} fix pass(es)).`) +
  ` Resume: the Resume_*.pdf in ${WS}/; run details: ${WS}/gaps.md.`

return {
  status:                        'done',
  workspace:                     WS,
  verdict:                       finalVerdict,
  iterations_used:               iterations,
  grounding_failures_first_pass: firstPassGrounding,
  num_gaps:                      (presentResult && presentResult.num_gaps) || 0,
  message,
}
