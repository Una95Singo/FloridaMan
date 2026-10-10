# FloridaMan v1 — the software

The working product behind the thesis: an agentic storm-watch loop for
hurricane-exposed catastrophe bonds. Agents trigger on NHC events, draft
traceable hypotheses, a mechanical QC gate validates the numbers, a human
expert judges the thinking, and reality scores the predictions. There is
no dashboard. The trace feed is the product.

This build mirrors the layout it will merge into on the `FloridaMan`
repo (`Una95Singo/FloridaMan`):

```
floridaman-build/
├── README.md            ← this file
├── DEPLOY.md            ← GitHub Pages + Actions + operator routine
├── site/                ← public surface (static, GitHub-Pages-ready)
│   ├── index.html       ← thesis summary + live watch status
│   ├── storms/isaias.html ← full run feed: hypotheses, traces, QC, corrections
│   ├── universe.html    ← the 10-bond universe + current read per bond
│   ├── method.html      ← the loop: draft → QC → expert → publish → score
│   └── style.css
└── pipeline/            ← the agent loop (Python, stdlib only)
    ├── floridaman/
    │   ├── ingest.py    ← NHC public products → normalized Advisory
    │   ├── triggers.py  ← material-change detection (TRG-001…003, silence)
    │   ├── draft.py     ← trace generator; Reasoner interface + stub
    │   ├── qc.py        ← the 8 QC checks as executable code
    │   ├── gate.py      ← expert gate via GitHub issues
    │   ├── publish.py   ← git-commit approved trace + QC record
    │   └── run.py       ← CLI: python -m floridaman.run --storm isaias --once
    ├── tests/test_qc.py ← 7 tests incl. the run-001 acceptance test
    └── .github/workflows/watch.yml ← 6h heartbeat
```

## How each part maps to the thesis

| Thesis principle | Implementation |
|---|---|
| Agents trigger; silence is correct | `triggers.py` — pure functions over (previous snapshot, advisory); `evaluate()` returns fired TRG ids or `[]`. `run.py` prints `SILENCE` and exits 0 when nothing fired. |
| Traceability is the product | `draft.py` writes `trace-<ts>.md` with Trigger / Inputs-and-sources / Exposure mapping / Hypothesis / Falsification / Where-am-I-wrong sections, byte-identical in shape to the real run-004 trace. `site/storms/isaias.html` renders the full feed. |
| Hypothesis-first, indicative ranges | The `Reasoner` protocol in `draft.py` owns the four judgmental sections; v1 ships a `StubReasoner` that labels everything STUB. Real reasoning plugs in without touching the pipeline. |
| Two kinds of wrong | `qc.py` implements the 8 mechanical checks from `agents-qc-reviewer-agent.md` and emits PASS/BLOCKED records shaped like the real QC records. A wrong hypothesis is the expert's business; a wrong number never reaches them. |
| User as senior expert | `gate.py` — on QC PASS, opens a GitHub issue with the hypothesis + "where am I wrong?" questions and pauses. `APPROVE` resumes; `CORRECT`/`REQUEST CHANGES` amends. |
| No dashboards | `site/` is a chronological feed. No charts-as-decoration, no cockpit UI. |

## Run it locally

```bash
cd pipeline
# one check now (prints SILENCE + exit 0 if no trigger fired)
python3 -m floridaman.run --storm isaias --once

# QC a draft trace (context: universe + latest advisory info)
python3 - <<'EOF'
from floridaman import qc
ctx = qc.QcContext(universe_csv_path="../bond-universe.csv",
                   latest_advisory_number="13A")
verdict, record_path = qc.review("watch/isaias/trace-20261010-001.md", ctx)
print(verdict.verdict)   # PASS or BLOCKED
EOF

# the test suite (includes the mandatory run-001 acceptance test)
python3 -m unittest discover -s tests
```

Requirements: Python 3.10+, stdlib only — no installs. The bond universe
CSV lives at `data/bond-universe.csv` in the repo; point `--universe` at it
or keep the default layout.

## What v1 deliberately does not do

- **No real reasoning.** `StubReasoner` emits a labeled template. A real
  `Reasoner` implementation is the operator's next build step; the
  interface is documented in `draft.py` and takes no credentials in code.
- **No autonomous publishing.** The workflow stops at the expert gate by
  design; `publish.py` commits but never pushes — push stays human.
- **No live NHC parsing in QC.** Check 4 (freshness) works from injected
  advisory identity; the workflow wires `run`'s `$GITHUB_OUTPUT` into it.
- **No secrets anywhere.** GitHub access in `gate.py` reads `GITHUB_TOKEN`
  from the environment only.
