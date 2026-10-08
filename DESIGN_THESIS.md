# FloridaMan — Design Thesis

*Reimagining insurance-linked securities work, zero-based. Not faster software. Different work.*

## 0. The mission

Prove that work can be done differently if we allow ourselves to think in new
boxes. FloridaMan is the proof: a live, public, open-source demonstration that
agentic workflows can replace — not accelerate — how ILS professionals deal
with hurricanes.

## 1. The provocation: acceleration is not reimagination

The industry is automating itself, and calling it transformation. Swiss Re's
CEO says the firm is "rethinking our company's core processes from the ground
up" with AI — and the flagship example is construction-insurance pricing going
from 25 steps across 14 applications to fewer than five applications. Fewer
screens. Still screens.

Their facultative reinsurance team receives 100,000+ deal submissions a year
and uses AI to triage them so underwriters can "focus their expertise on the
deals most likely to succeed." Genuinely impressive. Still triage. The workflow
underneath is untouched.

This is the pressure test our thesis has to survive: **if all we build is a
faster version of the current process, we have failed.** A better dashboard is
not reimagination. Ten screens instead of twenty is not reimagination.
Reimagination starts by throwing away UI/UX-driven thinking — the assumption
that work happens when a human opens an application and clicks through a
workflow — and asking what the work actually is.

## 2. The work as it exists today

Four workflows define life around hurricane risk in ILS:

1. **The 6am storm scramble.** A storm forms. Portfolio managers manually pull
   advisories, cross-reference holdings against exposure zones in spreadsheets,
   wait on slow, opaque dealer marks, and write a morning note under time
   pressure.
2. **The new-issue first read.** An offering circular lands. An analyst spends
   hours extracting trigger type, attachment/exhaustion, expected loss and
   spread, then assembles comps by hand to judge relative value.
3. **The loss-creep watch.** After landfall: months of manual tracking across
   PCS updates, sponsor announcements and news, watching whether a bond's
   attachment point is threatened.
4. **The "what if."** "What happens to my book if a Cat 4 hits Miami?" means a
   call to the modeler, a vendor run, a day's wait.

Every one of these is dominated by assembly, stitching, and waiting —
copy-pasting across Excels. The actual expertise (judgment about risk, about
price, about what matters) is a thin layer on top of a mountain of drudgery.

## 3. The reimagined division of labor

Zero-based, the work reorganizes around four principles:

**Agents trigger.** Nothing starts with a human opening an app. A storm being
named, an offering circular being filed, a PCS estimate updating — events
trigger agents. The human never "checks the system." The system comes to the
human, and only when there is something worth their judgment.

**Traceability is the product.** In regulated finance, an agent's output you
cannot audit is an output you cannot act on. Every number the agent produces
links to its source and its reasoning. The trace is not a log for debugging —
it is the shared ground truth between the agent and the expert, and the thing
compliance can inspect. If it isn't traceable, it doesn't ship.

**Hypothesis first, data second.** The agent does not present data and wait to
be asked what it means. It arrives with a hypothesis about the *so what*:
"three of your bonds are in the cone; here is my working; here is what I think
it means for the book." Data serves the hypothesis, not the other way around.

**The user is the senior expert.** The agent is an indefatigable junior
analyst with perfect memory. The human is the senior whose judgment is the
scarce resource. The interface between them is a standing question the agent
asks every time: *"where am I wrong?"* Corrections feed back into the agent.
Expertise compounds instead of repeating.

This is also what it is not: it is not agents doing all the thinking while the
human rubber-stamps. Judgment stays human — deliberately, structurally. Work
is using your skills to create value. The reimagination just finally lets the
skills be the work, instead of the stitching.

## 4. Why there is no dashboard

A dashboard assumes the user's job is to *look at things*. In the reimagined
workflow, the user's job is to *decide things*. Screens full of widgets
optimize for browsing; we are optimizing for the moment of judgment.

FloridaMan will have minimal visual surface: the public trace of what the
agent did, thought, and concluded — because traceability demands
inspectability. That is a record, not a cockpit. Anything that looks like a
traditional dashboard is a sign we slipped back into the old box.

## 5. The live proof

Thesis without demonstration is a blog post. FloridaMan proves the argument by
running it, in public:

- **Open-source agents.** The agent definitions — triggers, tools, reasoning
  contracts, output formats — live in `agents/` in this repo, free for anyone
  to read, fork, and run. The thinking is the open-source artifact, not just
  the code.
- **A public trace.** Every run publishes its full trace and hypothesis where
  anyone can inspect it. You can watch the agent think, check its sources,
  and see exactly where the expert corrected it.
- **Integrated with singolab.com.** The live watch is linked from the
  projects that document the work, so the demonstration and the writing about
  the demonstration live side by side.

The first live subject is Tropical Storm Isaias (October 2026) — a real storm,
watched in real time, with the agent's hypotheses timestamped against what
actually happened. There is no better audit than reality.

## 6. The business outcome, and for whom

The user is the ILS portfolio manager. The outcome is not information — it is
**decision advantage under time pressure**: act hours before dealer marks
move, and communicate to their own investors with total confidence about why.

Notice what disappears: the morning scramble, the blank-page memo, the months
of passive watching. The PM's job collapses to the highest-value act in
finance — judgment — applied at the moments of highest leverage. Everything
else belongs to the agent.

## 7. Roadmap

- **v1 — The watch agent, live.** Storm-triggered monitoring of
  hurricane-exposed bonds against a live storm (Isaias), publishing
  trace + hypothesis. This repo, this storm, now.
- **v2 — The first-read agent.** New-issue screening: circular in, structured
  terms and relative-value hypothesis out.
- **v3 — The creep agent.** Post-event monitoring against attachment points,
  exception-based.
- **v4 — The what-if agent.** Plain-language scenario questions, indicative
  answers in minutes, labeled as such.

Each version must earn its existence against the thesis in section 3. Anything
that becomes a dashboard gets deleted.
