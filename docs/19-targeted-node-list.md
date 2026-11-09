# 19 — Showing the consolidation model only the pages the search brings back (November 2026)

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

*Continues `docs/17` (§12 to §20 there, in this English write-up). Every protocol and threshold below was written down
before the run it governs; results are reported as they came, including the ones that went against us.*

## 1. The question

At every pass, consolidation sends the model the list of **all** existing pages (name, type, aliases), so that it
files a fact in a page that exists instead of creating another. That list grows with the memory: with a few dozen
pages it already costs as much as the raw text of a pass; with thousands it would dominate the input and eventually no
longer fit. Retrieval, on the other hand, only returns what is relevant — the very principle of the wiki and of the
graph. **Does the same search, run before filing, suffice?** What the model sees changes; alias resolution (a page the
model names is attached to the existing page) keeps the full list, as before.

## 2. Small scale: the agent's memory (53 to 83 pages)

Terra, adapted prompt, 12 days (two panels), two passes; at most 30 pages kept (search over the whole lot):

| | Correct answers | Coverage | Probable duplicates | Lost lots | Real input tokens |
|---|---|---|---|---|---|
| Full list | 71.4 % | 82.0 % | 13 (noise between its two passes) | 0 | 453,652 |
| **Targeted list** | **70.7 %** ✓ | **80.0 %** ✓ | **12** ✓ | **0** ✓ | **432,552** |

The list the model sees is halved with no measurable loss; at this size, no gain in tokens to speak of (−4.7 %).

## 3. Large scale: fused LongMemEval memory, gpt-4o-mini

Starting memory: the fused LongMemEval memory rebuilt **without** 40 drawn questions (seed 1105, no abstention) —
460 conversations, **2,129 pages, 2,607 nodes, 478 concepts, 3,546 facts**; the 40 questions' conversations are then
consolidated into it session by session (81 sessions), and the 40 questions asked. gpt-4o-mini, the model that built
that memory. (LongMemEval simulates **one** user: all facts carry `speaker:user`; conversations were written
separately, so two pages on the same subject may be two different things.)

| | Correct | Coverage | Probable duplicates | Lost | Input per pass | Consolidation cost per pass |
|---|---|---|---|---|---|---|
| Full list | 41.2 % | 56.5 % | 39 (noise) | 0 | 4.90 M tokens | $0.69 |
| **Targeted list (30 pages)** | **43.8 %** ✓ | **59.7 %** ✓ | **22** ✓ | **0** ✓ | **1.00 M** | **$0.20** |

All four thresholds hold; input ÷4.9, cost ÷3.4; with the targeted list the model files **more** facts into existing
pages (71-75 against 38-43) and creates 15 % fewer new pages. Search recall: 86 % of the pages the model chose with the
full list were in the selection.

## 4. Large scale with Terra: the threshold fails

Same protocol, Terra as consolidator:

| | Correct | Coverage | Probable duplicates | Input per pass | Cost per pass |
|---|---|---|---|---|---|
| Full list | 58.8 % | 88.7 % | 58 (noise) | 4.90 M | $5.24 |
| Targeted list (30 pages for the lot) | 61.3 % ✓ | 90.4 % ✓ | **103 ✗** | 1.05 M | $1.43 |

Terra really uses the full list: it files three times more facts into existing pages than gpt-4o-mini, making
connections of meaning a word search does not (a photography workshop filed under "workshops attended"). Search recall
falls to 61 %. Terra against gpt-4o-mini, same memory and questions: +17 points of correct answers, +32 of coverage,
twice the facts, half the new pages, about seven times the cost.

## 5. Why the ranking failed — and the fix

A free analysis (no model): the search **reaches** 98 % of the pages Terra chooses, but ranks them low. The cause: we
searched with the **whole session** at once (27 messages on average); a text that long directly touches 708 pages out of
2,129 (up to 1,137), and the global sort favours pages whose exact title appears, while Terra mostly chooses pages linked
by a single word of a longer title (44 of 54 missed pages). The search was designed for a message, not a session.

**Fix: search message by message**, keep the K best pages of each message, take the union (no sequencing: searches are
independent; the model still consolidates the session in one call; ≈ 20 ms per search at 2,800 nodes). Recall against
Terra's choices with the full list, measured without a model:

| Pages kept per message (K) | 5 | 10 | 15 | 20 | 30 |
|---|---|---|---|---|---|
| LongMemEval (2,129 pages) — recall | 60 % | 69 % | 78 % | 84 % | 92 % |
| — pages sent per session | 30 | 66 | 101 | 135 | 193 |
| Agent's memory (53-83 pages) — recall | 98 % | 100 % | 100 % | 100 % | 100 % |

At K = 30 the list is ≈ 4,000 tokens, ten times less than the full list.

## 6. Short words (acronyms)

Two pages the search never found ("5K run", "BBQ experience") were missed for the same reason: a single word of a title
only counts from 5 letters (4 for a distinctive word), and words under 3 letters are dropped — "5K" and "BBQ" were
invisible although the session said "BBQ" 36 times. Rule measured (bench variant, `banc/longmemeval/variante_sigles.py`):
a 2-to-4-letter word counts, exact match only, if it is not a stop word and is written **in capitals or with a digit in
a page title or alias** (BBQ, PC, 5K); short verb forms added to the French stop words ("ai", "va"…: *j'ai* must not
light up an "AI" page). Recall +2 points (91.9 → 94.0 % at K = 30); noise unchanged (+0.1 % pages touched at large
scale, +0.6 % on the agent); 14 acronyms admitted on the agent's memory, all real ones. Not yet in the search the agent
uses to answer — to be validated there separately.

## 7. Terra, message by message + acronyms (through the agent's subscription)

| Terra, 2,129 pages, 81 sessions, 40 questions | Correct | Coverage | Probable duplicates | Input per pass | Pages shown per session |
|---|---|---|---|---|---|
| Full list | 58.8 % | 88.7 % | 58 (noise) | 4.90 M | 2,129 |
| 30 pages for the session (§4) | 61.3 % | 90.4 % | 103 ✗ | 1.05 M | 30 |
| **30 pages per message + acronyms** | **57.5 %** ✓ | **91.1 %** ✓ | **70** ✗ (threshold 60) | **1.32 M** | **≈ 188** |

No fact was filed outside the list shown (0 of 273). The pre-registered duplicate threshold still fails, narrowly: the
excess over noise drops from 45 to 12 over 81 sessions. Which raised the question of what that measure counts (§8).

## 8. Duplicates, reviewed blind; a deterministic detector

The 51 distinct "probable duplicate" pairs of §4 and §7 (excluding the user's page) were labelled **blind** (condition
hidden, an independent reviewer, from names and summaries): D = the same thing under two names; G = one is a particular
case of the other (a dessert and the dinner where it was served); X = two different things (two people named Alex).

| Occurrences (excluding the user's page) | D (true duplicate) | G (granularity) | X (different) |
|---|---|---|---|
| Noise: full list, between its two passes | **0** | 11 | 27 |
| Per message + acronyms, against the full list | **2** | 11 | 31 |

**True duplicates are rare**: 2 in 162 consolidated sessions, both borderline according to the reviewer. Most of what
the measure counted is the model's own variability (filed here in a general page, there in a specific one) — and
specific pages stay linked to general ones in the graph, hence unchanged answers. This review came after the fact: the
pre-registered verdict of §7 remains a failure; a clean confirmation needs a blind duplicate measure fixed in advance.

**A deterministic duplicate detector** (`banc/catalogue/doublons.py`, no model: same name up to word order and plurals;
a shared multi-word alias; close names and the same graph neighbourhood) **found neither of the two true duplicates**
(their names differ) and **its proposals were almost all wrong** — mostly different people sharing a first name, whom a
merge would mix up; a first version, with 5-letter truncated roots, even matched "instacart" with "instagram".
**Conclusion: no automatic merging.** The direction kept for later is reconsolidation at read time (`docs/18` §4).

## 9. Observer mode on the agent

Before sending the targeted list in production, it is **observed** on the real memory: at each consolidation the
selection (30 pages per message) is computed and logged while the full list still goes to the model; afterwards the log
records which existing pages the model filed facts into and whether they were selected — recall measured on real life.
Setting `catalogue_observateur_k` (0 = off, the default); module `observateur.py`; log
`telemetrie/catalogue_observateur.jsonl`; reader `outils/lire_observateur.py`; `tests/test_observateur.py` (11 checks,
including a simulated failure that does not stop consolidation). On a copy of the real memory: 91 pages, 17 selected
for a two-message lot, 370 ms.

## 10. What we take from it

- At small scale, showing only what the search returns costs nothing; at large scale with a modest model, it divides
  the cost by 3.4 and reduces duplicates.
- With a model capable of connections of meaning (Terra), searching the whole session ranks badly; searching **message
  by message** recovers 92 % of its choices with ten times less list, and no answer is lost.
- "Duplicates" were mostly a measurement artefact; true ones are rare, and a name-based detector does more harm than
  good.
