# BOOTSTRAP.md — brief for the first Claude Code session

Read this file completely before doing anything. It tells you what this project is for, what to base your decisions on, and what your task is in this session. It is not a description of the codebase — writing that description is your job.

Delete this file once `CLAUDE.md` and `PLAYBOOK.md` exist and are accurate. It is scaffolding, not documentation.

---

## 1. What this project is for

Polispeech is a research pipeline for parliamentary text. It currently covers the Chilean congress. The point of the next phase of work is to make it possible to add other parliaments without rewriting the pipeline, and to make the collection step reliable enough to run unattended over a long job — for example, downloading every law passed within a given election cycle.

Two audiences drive the design:

- **Research.** Results must be reproducible. Someone should be able to re-run the analysis from raw inputs and get the same corpus.
- **Work.** This may be proposed as a tool for a team. That means installable, documented, tested, and legible to someone who did not write it.

Neither audience is served by cleverness. Both are served by boring, obvious structure.

---

## 2. Principles to base your proposals on

When you have a choice, these are the tiebreakers. They are ordered — earlier ones win.

1. **Separate fetching from parsing.** Fetching touches the network, saves raw bytes to disk, and records what it saved. Parsing reads only from disk. A parser bug should cost a re-parse, never a re-scrape.
2. **Long jobs must be resumable and idempotent.** Killing a run and restarting it should lose nothing and duplicate nothing. Job state lives in a file, not in memory.
3. **One adapter per source.** Everything specific to a parliament lives behind a common interface. Everything downstream of that interface is source-agnostic and does not know where the text came from.
4. **Validate at ingest.** A document that fails schema validation fails loudly when it is collected, not silently at analysis time.
5. **Tests run offline against saved fixtures.** Real pages saved to disk, parsed in a test, no network.
6. **Prefer the standard layout over a custom one.** `src/` package, `tests/`, `pyproject.toml`. Do not invent conventions where conventions exist.
7. **Data is not code.** Nothing under `data/` is committed.

If a proposal of yours conflicts with one of these, say so explicitly and explain the tradeoff. Do not quietly resolve it.

---

## 3. Recommended target structure

This is a target, not an instruction to reorganise the repo today. See section 5 for what to do with it.

```
polispeech/
├── CLAUDE.md                  # what this repo is, conventions, working rules
├── PLAYBOOK.md                # how work gets done here; decisions as they are made
├── HANDOFF.md                 # rewritten at the end of every session
├── README.md                  # for a human who found this repo
├── pyproject.toml             # dependencies, package metadata, tool config
├── .env.example               # names of required env vars, no values
├── .gitignore
│
├── .claude/
│   └── commands/              # saved workflows, invoked as /scope, /handoff …
│       ├── scope.md
│       ├── handoff.md
│       └── newsource.md
│
├── docs/
│   ├── style/                 # samples of my own writing, for voice matching
│   ├── decisions/             # one short file per non-obvious decision
│   └── sources/               # per-parliament notes: URLs, quirks, rate limits, legal basis
│
├── src/polispeech/
│   ├── config.py              # paths, settings, env loading
│   ├── models.py              # Pydantic schemas — the common document contract
│   ├── cli.py                 # entry point
│   │
│   ├── sources/
│   │   ├── base.py            # the adapter interface every source implements
│   │   └── chile/
│   │       ├── discover.py    # what documents exist in a given range
│   │       ├── fetch.py       # network only, writes raw bytes
│   │       └── parse.py       # disk only, returns validated models
│   │
│   ├── store/
│   │   ├── raw.py             # where raw payloads go, how they are named
│   │   ├── state.py           # SQLite job state: queued / fetched / parsed / failed
│   │   └── corpus.py          # the processed output
│   │
│   ├── pipeline/
│   │   ├── ingest.py          # orchestrates discover → fetch → parse
│   │   └── normalize.py       # cleaning, dedup, canonical text
│   │
│   └── nlp/                   # analysis; consumes the corpus, never the network
│
├── tests/
│   ├── fixtures/              # real saved pages, small and committed
│   ├── test_models.py
│   └── test_parse_chile.py
│
├── scripts/                   # one-off and operational scripts
├── notebooks/                 # exploration; not part of the pipeline
└── data/                      # GITIGNORED
    ├── raw/                   # exactly what came off the network
    ├── interim/
    └── processed/
```

### The adapter interface

The generalisation to other parliaments lives or dies on this. Roughly:

```python
class Source(Protocol):
    name: str

    def discover(self, start: date, end: date) -> Iterable[DocumentRef]: ...
    def fetch(self, ref: DocumentRef) -> RawPayload: ...
    def parse(self, raw: RawPayload) -> Document: ...
```

`Document` is defined once, in `models.py`, and is the same for every parliament. Adding Spain means writing `sources/spain/`. It should mean touching nothing else.

If the existing Chilean code cannot fit this shape, that is useful information. Say what does not fit and why.

---

## 4. Language and style

These rules apply to prose: documentation, README, commit messages, comments, anything written for a human to read. They do not apply to code.

**Do not use:**

- Em-dash-heavy sentence rhythm.
- Three-item lists where two items would do.
- Sentences of the form "It's not just X, it's Y."

<!--
This list is deliberately short and will grow as I notice things.
Add to it only when I ask. Do not extend it on your own initiative,
and do not infer additional rules from the ones above.
-->

Beyond that: match the voice of the samples in `docs/style/` when that folder has content in it. Until it does, write plainly and do not compensate with adjectives.

---

## 5. Your task in this session

Do these in order. Stop after step 4 and wait.

1. **Read the repository.** Files, structure, entry points, dependencies, what actually runs. Do not change anything.

2. **Write `CLAUDE.md`.** Describe what is there — the real structure, the real conventions, how to run it, what the moving parts are. Describe the repo as it is, not as it should be. Copy section 4 of this file into it verbatim. Keep it short enough that it stays useful late in a long session.

3. **Write an audit.** In plain prose, not a table: what the current structure does well, where it diverges from section 3, and which divergences actually matter versus which are cosmetic. Be specific about files.

4. **Propose a migration.** Ordered, small, each step independently useful and independently revertible. For each step say what breaks if it is done wrong. Optimise the ordering for the pipeline staying runnable throughout, not for reaching the target structure quickly. Flag anything you think is a bad idea in section 3 given what you found.

Then stop. Do not begin the migration. I will pick a step and start a fresh session for it.

---

## 6. How we work here

- One session, one task. When this session's task is done, the session ends.
- Before writing code, state which files and functions you will modify and what you will leave untouched. Wait for confirmation.
- When you propose an approach, say what it makes harder later.
- At the end of a task, state what you did not do — skipped cases, deferred cleanups, things you were unsure about.
- Push back when a request departs from settled practice or risks wasted work. Not on style preferences.
- Rewrite `HANDOFF.md` before the session ends: current state, what changed, what was left untouched, the next single task, anything known-broken.
