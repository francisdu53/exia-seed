# 21 — The watch: recall by convergence of voices (EXIA SEED 0.9.16, November 2026)

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

*Continues `docs/06` (recall), `docs/08` (concept fields) and `docs/11` (memories that come back on their own). The
automatic recall of 0.9.15 lit **pages** (by name, by one word of a name, by concept fields, by full-text hits) and then
picked facts inside them. The watch lights **facts** directly, gives each fact its own score from several independent
voices, and keeps only the facts likely to help. No language model, no vectors.*

## 1. Why

A recall bench on the agent's real messages (blind judge, wide candidate pool, 131 messages) traced where useful
memories were lost in the 0.9.15 funnel:

| Where a useful memory stopped | Share of useful memories |
|---|---|
| its page was never lit | 40 % |
| page lit, score below 0.35 | 10 % |
| cut by fixed quotas (1,200 tokens, 4 per page) | 16 % |
| kept, score below 0.50 | 2 % |
| cut by fixed quotas (3 subjects × 2 facts) | 10 % |
| **given to the agent** | **21 %** |

Each gate removed useful and useless facts at almost the same rate (8 % useful at the entrance, 22 % at the exit). The
door was the page, the score was mostly the page's activation, and fixed quotas cut good facts.

## 2. The five gears

1. **Facts light up.** All sources at once, at the fact level: full text (BM25 over every fact, top 60), the notions of
   the thematic maps (top 30), the facts of pages named in the message (full alias or one alias word), and the facts of
   the 5 pages the graph propagation activates most. A page is present only because one of its facts is.
2. **Each fact gets its own score — one primitive.** With `cab_pull(a, b, t) = a + (b − a)·t`:
   - start from a small leak `s₀`;
   - for each voice `v` of strength `x_v ∈ [0, 1]`: `s ← cab_pull(s, 1, w_v · x_v)` (the voice pulls towards 1);
   - for each expected voice `u` that is absent: `s ← cab_pull(s, 0, p_u · (1 − x_u))` (its absence pulls towards 0).

   This is a noisy-OR with inhibitors: every piece of evidence raises the chance, every missing one lowers it. Weights
   are fitted once by maximum likelihood on judged facts, so **the score reads as the probability that the fact helps**
   (calibration: score 0–0.1 → 6 % useful, 0.2–0.3 → 26 %, 0.3–0.5 → 42 %, ≥ 0.5 → 80 %).

   | Voice | Strength | Weight (pull to 1) | Absence (pull to 0) |
   |---|---|---|---|
   | page named in full | 0 / 1 | 0.30 | — |
   | rare words shared (BM25 rank) | 1 / (1 + rank) | 0.28 | — |
   | **lived link** (said in the same message or a neighbouring line as an anchored fact, or naming it) | link strength | 0.24 | — |
   | one word of the page name | 0 / 1 | 0.23 | — |
   | concept (theme) lit by the message | relative activation | 0.10 | 0.21 |
   | work rule (procedural section) | 0 / 1 | 0.05 | — |
   | graph activation of the page | relative | 0.02 | — |
   | notion of the message (or linked to one) | 1 or link weight | 0.01 | 0.23 |
   | share of the message in the fact | coverage | ≈ 0 | **0.61** |

   A concept or notion voice is *expected* only when the fact carries a theme: a memory without a thesaurus is not
   silenced for lacking them.
3. **Choice without quotas.** Facts scoring ≥ 0.20 (at least one chance in five to help), at most 10, with the 1,200-token
   cap only as a safety net. Nothing passes → silence.
4. **Continuity.** A fact already given in the last 3 hours of the conversation is not given again (the host replays
   earlier blocks; the agent still has it). A message too short to name its subject (« yes, go ahead ») is read together
   with the previous message (< 30 min).
5. **Presentation.** Each fact arrives whole, under its page and the page's summary, with **why** it came back (« you
   named … », « said together with … », « same theme: … », « shared words: … »). The recall log keeps every given fact
   in full with its score and reason — the ground for learning from use later.

Setting: `rappel_moteur: montre` (default `ancien`, the 0.9.15 recall, so that installing 0.9.16 changes nothing until
the setting is switched; switching back needs no redeploy).

## 3. What was measured

All recall measurements are on the agent's real messages, on samples **never used for tuning**, judged blind by the
agent's own model (« useful for this message », strict).

| Fresh sample | 0.9.15 useful / given (precision) | watch useful / given (precision) | messages better / worse |
|---|---|---|---|
| 100 messages | 20 / 99 (20 %) | **47 / 213 (22 %)** | 24 / 4 |
| 100 messages (unbiased) | 25 / 106 (24 %) | **49 / 195 (25 %)** | 22 / 5 |
| 100 messages | 23 / 118 (20 %) | **38 / 178 (21 %)** | 17 / 5 |

**About twice as many useful memories, at equal precision.** Cost: about 2× the injected tokens (≈ 200 tokens per
message on average). Latency: 3 ms median, 10 ms p99 on the agent's memory (≈ 1,100 facts); 10 ms median, 20 ms p99
on 3,901 facts.

**Answers.** On 74 messages, the agent answered with each block (same persona, same previous turns, no tools) and a
blind judge ranked the answers: the watch won 43 duels, 0.9.15 31; both beat « no memory » clearly (27–7 and 23–11 on
messages where memory mattered). Mean scores stay close; the trend is clear but not yet statistically decisive.

**Public benchmarks — corrected on 23/11/2026.** The table first published here was measured with a development
version of the watch, before a last-minute rule of 0.9.16 (a missing theme counts against a fact only if the fact has
a theme). On the agent's memory the rule changes nothing (1,111 of 1,112 facts have a theme), but on benchmark
memories only 81 % (LoCoMo) and 51 % (LongMemEval) of facts have one: the released 0.9.16 returned the same lists as the
measured version for only 68 of 196 LoCoMo questions and 12 of 100 LongMemEval questions. The released 0.9.16 was
re-measured with the protocol of `docs/22` (fused memories, a 450-token block, reader GPT-6.1 Terra « high », judge
Terra « low » — not comparable to published leaderboards):

| Fused memory, test questions | `memoire_chercher` (0.9.15) | watch 0.9.16 (search mode) |
|---|---|---|
| LoCoMo, 196 questions | 46.4 % | 43.9 % |
| LongMemEval, 100 questions | 43 % | 45 % |

On the larger verdict sets of `docs/22` (796 LoCoMo and 450 LongMemEval questions) the watch scored 43.0 % and 48.2 %.
The two engines stay within a few points of each other, as first reported; the per-question-memory figures and the
recall-mode figures of the first version are withdrawn (they were not re-measured). The real-use results above are
unaffected: they were measured on the agent's own memory, where the rule changes nothing. The watch's value is the
**automatic recall**, where 0.9.15 was weak — and `docs/22` describes what replaced it on the benchmarks.

## 4. What did not work (kept for the record)

- **Notion links that learn** (Hebbian reinforcement of map links when they lead to a useful fact, measured
  « test then learn » in time order on 372 judged messages): no gain (16 % vs 16 %) — a given pair of notions recurs
  too rarely.
- **A « strength » voice per fact** (what helped before gets stronger): +4 points in the time-ordered measure, but no
  gain on fresh messages (38 / 216 vs 38 / 178): the prior strength of never-judged facts lifted every score and simply
  made the recall talk more. The real signal will be **use** — facts the agent actually reuses in its answers — logged
  from 0.9.16 on.
- **Notions, named pages and the graph as sources** add nothing beyond full text and lived links (removal study); the
  concept voice still matters inside the score.

## 5. Limits

- Weights and threshold come from one user's memory; a new user may need the threshold recalibrated.
- The judge is a model; usefulness « for this message » underrates context that only matters later in a conversation.
- The benchmarks' ceiling is consolidation (what is written), not recall: with the whole memory in context instead of
  12 facts, LongMemEval answers rise only a few points; with the raw conversations, by 20+ points (`docs/13`).
