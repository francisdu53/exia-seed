# 18 — The memory lifecycle (specification and first measurements, November 2026)

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

*Phase 3 of the spec ("living memory"). Forgetting is coded and tested but not switched on in production; the
duplicate detector was tested and rejected (`docs/19` §8).*

## 1. Why

A memory that only grows ends up as noise: at large scale, a single message directly lights up 279 pages out of 2,129
(`docs/19` §6), the consolidation list swells, so does memory. The brain prunes, consolidates, reorganises and forgets.
EXIA GHOST, the project EXIA SEED derives from, had designed this (maps that split, merge, are born and disappear;
memories that decay); much of it is not coded there, and its map lifecycle relies on embeddings. We keep the
**principles**, with the signals EXIA SEED has: actual usage, dates, the graph. Because the graph is computed from the
wiki pages at every consolidation, **one mechanism serves both**: forget a fact in the wiki and its links leave the graph
at the next computation; empty a page and its node disappears.

## 2. The life map (measured)

`outils/carte_de_vie.py` (read-only): for each page, its usage at four levels read from the existing logs — **touched**
(lit up by the search), **shown** (given to the agent by automatic recall), **found** (returned by `memoire_chercher`),
**read** (`memoire_lire`). On the agent's real memory, logs from 26/09 to 06/11/2026:

| | Value |
|---|---|
| Pages | 92 (778 facts) |
| Never used (never shown, found nor read) | **50 (54 %)**, carrying 155 facts (20 %) |
| Among pages 30 days old or more | 10 of 34 (29 %) |
| Unused for 30 days or more | 12 |

Limit: the agent can also open a page with its ordinary file tools, which is not logged; dead weight is overestimated.

## 3. Forgetting, under conditions

**Decision: forget what is no longer used, except what a condition protects.** The unit is the **fact**; a page with no
facts disappears.

**Decay.** Each fact has a strength `s = exp(−Δt / τ)`, Δt = days since its last reinforcement (when it was said, or the
last time its page was shown, found or read). τ per section: episodic and prospective 30 days, semantic 30 days,
procedural 90 days (§9 for why episodic is not 7). **A fact is forgotten when s < 0.05** (about 3τ without use).

**Non-forgetting conditions** — a fact that meets one does not decay:
1. **A recurring date**: the fact carries a deadline or an event date on a recurring subject (birthday, contract,
   insurance, subscription, warranty, vehicle inspection, taxes…) — detected from the structured fields first, then
   from the concept, not from a word list alone.
2. **Protected**: `protected: true` (life events, set by consolidation).
3. **Requested**: the fact comes from a "note this" entry — the user wanted it remembered.
4. **Protected categories**: the user's and the agent's own pages, instructions given to the agent (`etat_agent`), and
   the concepts in a per-memory, user-editable list (default: family, health, billing, contract, insurance, legal,
   birthday).

**What happens to a forgotten fact.** It leaves its page; it is written to the forgetting register
(`oublis/YYYY-MM.jsonl`: text, metadata, page, date, reason); the raw log and git keep the trace; a tool restores it.
This is not the user's own retraction ("forget what I just said"), which stays immediate and complete.

**When.** At night, after consolidation, with no model call; a single writer (the consolidation lock).

## 4. Merging (duplicates)

Count pairs of pages lit up together at read time; at night, inside the existing consolidation call, show the model
the most **significant** pairs (≈ 150 tokens each) — not the most frequent: on the agent, the most co-activated pairs are
its instruction pages, lit by almost every message (36 to 51 co-activations over 488 messages). Pairs are ranked by
pointwise mutual information, log P(a,b) / (P(a) P(b)); the agent's instructions and the user's and agent's pages are
excluded. The decision is kept in both page headers (`distinct_de`, with a hash of both summaries), so a pair is not
asked again unless a summary changes; the merge itself is deterministic code, provenance kept. At the measured volume
(2 true duplicates in 162 sessions, `docs/19` §8), not built yet.

## 5. Splitting

A page that becomes a catch-all (many facts, concepts falling into groups that do not touch) is proposed at night to
the model, which names the sub-pages; code moves the facts with their source. Not built.

## 6. Creation

"Orphan" words (unknown to the memory) are already computed at every search. An orphan that comes back over several
days becomes a concept candidate for the next consolidation. Not built.

## 7. Build order

1. Life map ✅ · 2. Forgetting under conditions and its bench (§8-9) ✅ · 3. Co-activation counter and merging ·
4. Splitting · 5. Creation. Each step: a setting off by default, tests, a bench, then deployment on approval.

## 8. The lifecycle benches

**Time bench** (`banc/cycle/banc_du_temps.py`, retrospective, no model): replay the memory's real history day by day;
at each date the rules say what would be forgotten; the logs then say whether it was **asked for again** later (page
shown, found or read after the forgetting date — "page regret"; the fact itself among later recall candidates — "fact
regret").

**Recall bench** (`banc/longmemeval/oubli_reponses_lme.py`, LongMemEval): questions there ask about old details never
recalled in between — the worst case for forgetting. Same retrieval, reader and judge as `docs/13`, before and after
forgetting, on the day of each question.

## 9. Results (7 November 2026)

**Code**: `oubli.py` (the plan, writing nothing; applying it, which removes facts and empties pages, with the
register; restoring); `tests/test_oubli.py`, 19 checks.

**Time bench** (the agent's real memory, 41 days replayed):

| τ episodic and prospective | Facts forgotten in 41 days | Page regret | Fact regret |
|---|---|---|---|
| 7 days (the spec's starting value) | 41 (34 past intentions, 7 episodic; 6 pages emptied) | 2 (4.9 %) | 6 (14.6 %) |
| **30 days (kept)** | 0 — nothing reaches 3τ yet | — | — |

At 7 days, the "regrets" were mostly expired reminders ("remind me Tuesday to call X") resurfacing as candidates when
the person came back in the conversation: noise rather than loss.

**Worst case, LongMemEval**:

| τ episodic and prospective | Questions affected (of 500) | Correct before → after | Lost / gained | Effect on 500 | Cost |
|---|---|---|---|---|---|
| 7 days | 106 (dates 51, updates 55) | 61 → 43 | 25 / 7 | **−3.6 points** | $0.05 |
| **30 days** | 38 (dates 12, updates 26) | 23 → 19 | 7 / 3 | **−0.8 point** | $0.02 |

At 7 days forgetting is too aggressive (it costs date and knowledge-update questions); at 30 days the cost drops to
0.8 point in the worst case, and real use reinforces what matters. **τ = 30 days kept.**

## 10. Dates computed by code (8 November 2026)

**Principle: whatever can be done deterministically, reliably and simply is done by code; the model only handles the
particular cases.** The anchor is when the sentence was **said** (`dit_le`, the raw timestamp), never the time of the
consolidation, which may run days later.

`temps.proposer` (no model): written dates ("12/11", "3 March"), relative words (tomorrow, the day after tomorrow,
yesterday, today, tonight), weekdays (the next one of that name, the previous one if said "last" — the rule already used
to check dates), "in 3 days / 2 weeks", the time of day; nothing when the line carries several dates (left to the
model). The same rules as the check of a model's dates, run the other way.

**Two defects found while building it, fixed** (`tests/test_dates_code.py`, 15 checks): "yesterday" was recognised
inside another word (French "hier" inside "fichier", *file*) — including by the **check** of a model's dates in
production; a decimal number or a percentage could be read as a date.

**Against the models** (first panel, new facts of one pass):

| | Astra | Terra (adapted) | Luna (40,000) | Luna (10,000) |
|---|---|---|---|---|
| Facts carrying an event date | 30 | 42 | 19 | 26 |
| … code finds the same | 6 | 6 | 5 | 6 |
| … code finds another | 1 | 1 | 2 | 2 |
| … no date expression in the line (same day: redundant with `dit_le`) | 23 | 35 | 14 | 18 |
| Dates found by code only | 3 | 5 | 2 | 4 |

On the disagreements, code is right on "I'll look at it tomorrow" and "an invoice dated 23 January" (the model had put
the conversation day); both are defensible on "an e-mail received yesterday"; code is wrong when the cited passage is a
long assistant answer containing another date. Rule to measure next: a short message with a single date → code decides;
a long passage → the model proposes, code checks.

## 11. The daily lot (9 November 2026)

Setting `fermer_lot_fin_de_session` (true by default: the previous behaviour). When false, the end of a session no
longer closes the raw lot: it keeps filling across sessions and closes at `seuil_lot_tokens` (10,000 on the agent) or
every night (the 23:55 job) — one consolidation per 10,000-token lot, or one per day, and a clean memory every morning.
Before: one lot per session end (160 to 760 tokens according to the telemetry), hence 1 to 6 passes a day, each paying
the instructions and lists again. Raw writing and consolidation stay independent (separate process, separate locks;
consolidation only reads closed lots). Trade-off: a fact said in the morning enters the wiki in the evening, or at the
threshold; within the same conversation the agent has it in front of it, another session of the same day does not find
it through recall. `tests/test_lot_journalier.py` (4 checks).
