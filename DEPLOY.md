# FloridaMan v1 — deploy guide

## 1. The site → GitHub Pages

The `site/` directory is static HTML/CSS with relative links only — no
build step.

1. Copy `site/*` to the repo's publishing location:
   - **Option A (simplest):** repo root `docs/` folder, then
     Settings → Pages → Source: *Deploy from a branch* → `main` → `/docs`.
   - **Option B:** a `gh-pages` branch containing the `site/` contents
     at its root.
2. Refresh cadence: `index.html` inlines `watch/isaias/latest.md`
   (marked with an HTML comment). After each published run, copy the new
   `latest.md` content into that block, and append the new run to
   `storms/isaias.html` following the existing pattern (badge, trigger,
   hypothesis, falsification, QC verdict, expert corrections,
   `<details><pre>` full trace).
3. `universe.html` was generated from `bond-universe.csv` — regenerate
   the table if the universe changes; never hand-edit figures.

## 2. The pipeline → GitHub Actions (6h heartbeat)

1. Copy `pipeline/floridaman/` and `pipeline/tests/` into the repo
   (suggested: `pipeline/` at repo root, so the existing
   `watch/<storm>/` and `bond-universe.csv` paths resolve).
2. Copy `pipeline/.github/workflows/watch.yml` to `.github/workflows/`.
3. The workflow runs every 6 hours:
   `run` → (on draft) `qc` → (on PASS) `gate` opens the expert-review
   issue → **stops by design**. Exit code 2 from QC (BLOCKED) fails the
   job visibly; that is the intended alarm.
4. No extra secrets required. The workflow uses the built-in
   `${{ secrets.GITHUB_TOKEN }}` for the issue gate. Optional:
   `vars.NHC_ADVISORY_JSON` — pinned advisory-vintage JSON passed to
   QC's check 4 so it can detect figures wearing a newer advisory's
   label (see `watch.yml` comments).

## 3. Secrets (the complete list)

| Secret | Where | Used by |
|---|---|---|
| `GITHUB_TOKEN` | built-in, Actions | `gate.py` issue open/read |
| *(none)* | — | everything else |

There are no API keys. NHC products are public. If a real `Reasoner`
(LLM) is plugged into `draft.py` later, its credential lives in the
operator's environment — never in code, never in the repo.

## 4. The operator's daily routine (v1, human-supervised)

The pipeline is operated, not autonomous. Each day while a storm is
active:

1. **Morning:** check the Actions tab — green heartbeat = silence or a
   draft in progress; red = QC BLOCKED something (read the record,
   fix the draft or the data, re-run).
2. **On a draft:** QC runs automatically. If PASS, the expert-review
   issue opens — this is the human's inbox. Review the hypothesis,
   comment `APPROVE` or `CORRECT: <what changed and why>`.
3. **On approval:** run `publish.py` (or the documented manual step)
   to commit trace + QC record to `watch/<storm>/`, then push.
   Publishing without the expert's `APPROVE` is a defect — the design
   halts rather than bypasses.
4. **Refresh the site** (step 1.2 above) so the public feed matches the
   repo.
5. **After dissipation:** within 72h, write the scorecard — every
   timestamped hypothesis scored against what happened, hypothesis
   errors separated from mechanical errors. Then close the storm
   directory.

## 5. What "done" looks like per storm

A closed `watch/<storm>/` directory: every material advisory traced,
QC records beside each trace, expert corrections recorded with
attribution, a final hypothesis, and a post-event self-score. That
directory is the audit trail the thesis promises.
