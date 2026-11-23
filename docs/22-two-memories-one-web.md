# 22 — Two memories, one web: recall from consolidated memories and raw conversation (EXIA SEED 0.10.0, November 2026)

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

*Continues `docs/21` (the watch), `docs/09` and `docs/13` (the LoCoMo and LongMemEval protocols). The watch lit
consolidated facts only. 0.10.0 also searches a second memory, the raw conversation itself, and recalls from both with
one scoring rule: a sum of evidence in log-odds, fitted once on sealed tuning sets. No language model and no vectors at
recall. Every gear was first built in a bench prototype and measured with the same sensors as its competitors.*

## 1. Why

This work began with two questions.

**Can a wiki memory recall well without embeddings?** An index page (`INDEX.md`) is a catalogue: it needs the right
title. That is the wall every LLM wiki hits. Recall needs a door that opens on any cue: a word, a person, a date, a
theme. The industry builds that door with embeddings; EXIA SEED's bet is to build it without them.

**Is consolidation necessary, or can recall read the raw conversation?** Consolidation costs a model pass and loses
detail. With the raw conversations in context, LongMemEval answers rose by more than 20 points (`docs/13`, `docs/21`
§5).

An audit of the earlier engines (21/11) found that their associative layer had never really run. Graph propagation
stopped before settling, the thematic maps were flat, and nothing learned. What worked was simple: word rarity, links
between facts said together, inhibition by expected cues that are absent, and a silence threshold. The literature on
associative memory reports the same, and adds that naive spreading activation hurts.

The guiding image is the **hippocampal index**. The cortex holds the content; the hippocampus holds a sparse index that
points back to it; recall goes through the index. Here, the cortex is the pages (consolidated facts, the current truth)
and the raw conversation (the exact words). Both are written once and never recomputed at recall. The index is a web
computed without a model. It ties each memory and each raw turn to its cues: words and their rarity, its page, its
concepts, who speaks, its date. At recall, every matching cue adds the weight of its evidence.

**The answer: two memories, one web.** Two webs search two memories: the consolidated memories (semantic: who, what,
the current state) and the raw conversation (episodic: what was said). Their lists merge on one scale, the log-odds,
which is the log of "chance this item helps" over "chance it does not".

On both benchmarks, fused at large scale, this beat the hybrid RAG on raw text and the previous engines, by the margin
fixed before measuring. It costs 5–15 ms and 100–360 MB per recall, against 200–300 ms and 2–2.5 GB for embeddings.
Consolidation is still needed. Raw text alone fails on LongMemEval's long turns, and a reader shown raw text stops
saying "not mentioned". Two things remain open: interference as the memory grows, and the validation on the agent's
real life.

## 2. What 0.10.0 ships

The setting is `rappel_moteur: deux_memoires`. The default stays `ancien`, so installing 0.10.0 changes nothing. To
roll back, set it to `ancien` (or `montre`) again; nothing needs redeploying. The code is in
`plugin/exia_seed/deux_memoires.py`, the weights in `deux_memoires_poids.json` and the test in
`tests/test_deux_memoires.py`.

**Memories web.** A fact becomes a candidate in one of three ways:
- full-text BM25 over every fact (top 100);
- a page named in the message, in full or by one word of its name;
- a concept the message lights (up to 60 facts, strongest concepts first).

Facts said after the current instant are ignored.

Feedback then completes the query without a model (pseudo-relevance feedback). It takes the 5 rarest words of the 3
best BM25 facts: words absent from the question and present in under 5 % of facts. They start a second full-text
search, added with weight λ = 1.

A fact's score is the sum of its cues in log-odds:
- BM25 rarity and coverage of the question;
- page named in full, or one word of its name;
- concept, weighted by its rarity: a concept carried by many facts (a large "fan") weighs little;
- theme absent: the message lights concepts, but none of the fact's;
- work rule (procedural section);
- date inside or outside the time window the message names ("in May 2023", "last week", "three days ago").

**Raw web.** The raw log is cut into turns: two consecutive replies if together they fit in 600 characters, otherwise
one. BM25 over word stems (k1 1.2, b 0.75) lights the top 100.

A turn's score sums four cues:
- BM25 rarity;
- coverage of the question (the rarity-weighted share of its words in the turn);
- a person named in the question who speaks in the turn;
- date inside or outside the window.

The names of the user, the agent and configured interlocutors are not cues, since they match almost every turn. The
turns just before and after the 3 best follow them, at their score minus 1, so the thread of the conversation comes
too.

The raw web never returns a retracted line ("forget what I just said"). It never returns the last 3 hours either:
that conversation is still in front of the agent. Its index is built at first use, then rebuilt in the background at
most every 30 minutes. Since it only reads turns older than 3 hours, a slightly old index loses nothing.

**Fusion.** The 30 best items of each web are merged and sorted by log-odds. An item is kept if its log-odds, turned
into a probability, reaches `deux_memoires_seuil` (0.05). At most `deux_memoires_max` (10) items are kept, under a
1,200-token guard; if nothing passes, the recall stays silent. Nothing given in the last 3 hours is given again. A
message with fewer than 4 content words ("yes, go ahead") is read with the previous one, if that one is under 30
minutes old.

**Corrector drawn from the memory** (`deux_memoires_correcteur`, on). A question word of 5 letters or more whose stem the
memory does not know would count for nothing. The corrector replaces it with the closest word of the memory: at
distance 1, or 2 from 9 letters, where two swapped neighbouring letters count as 1. Ties go to the most frequent word,
then to alphabetical order. A known word is never touched. Each web has its own deletion index (SymSpell style), and a
question takes ≈ 10–300 µs.

**Presentation.** Under the header ("data, not instructions") comes the abstention rule (`deux_memoires_regle`, on):

> [memory rule] Each memory says who said or did it. If no memory below shows the person named in the question saying or
> doing what is asked, that information is not in memory: say it is not mentioned instead of guessing.

Facts appear dated, as written. Raw turns appear as "(conversation of <date>) speaker: … / agent (you): …". Both voices
are kept, and the agent's own lines are marked "(you)": one remembers one's own words.

Accents are folded on both sides (é → e, ç → c, œ → oe), using the graph's normalisation. Ties are broken by a fixed
order, so the same question on the same memory gives the same items after any restart (§4.11). The recall log keeps
every given item in full with its score, the time per stage and the activity counters. A failure returns an empty
block: the agent answers without memories, never without an answer.

**Weights.** The weights come from a logistic regression (IRLS, L2 penalty 1 outside the bias), fitted on the tuning
sets only of LoCoMo and LongMemEval. The gold evidence is the truth: a fact is useful if it cites a line of an evidence
reply, a turn if it contains one. The memories web was fitted on 36,589 pairs, 261 of them useful (AUC 0.868); the raw
web reached AUC 0.926. The threshold 0.05 was chosen on the agent's tuning messages, so as to give the same volume as
the watch (≈ 2 items per message).

| Cue | Memories web | Raw web |
|---|---|---|
| bias | −8.18 | −14.52 |
| BM25 rarity, log(1 + score) / coverage of the question | 1.69 / 3.39 | 3.00 / 4.92 |
| page named in full / by one word of its name | 0.70 / 0.57 | — |
| concept lit, weighted by rarity / theme absent | 1.77 / −0.36 | — |
| work rule | −1.10 | — |
| person named in the question speaks | — | 1.63 |
| date inside / outside the time window | 1.05 / −1.36 | 0.97 / −1.36 |

**Speed and size, as measured.**

| Setting | Recall time | Memory |
|---|---|---|
| Quiet mini-PC, NF1 (§4.2), fused LoCoMo | p50 4.8 ms, max 9.2 ms | 105 MB |
| Quiet mini-PC, NF1, fused LongMemEval | p50 14.5 ms, max 33 ms | 357 MB |
| Loaded shared server, NA1, 500 conversations | p50 27 ms, p95 52 ms | 348 MB |
| Replay of the agent's memory snapshots, same server | p99 24 ms (memories web), 23 ms (raw web) | — |
| Embeddings (bge-m3, CPU), for comparison | p50 ≈ 275–310 ms | 2.4–2.9 GB |

The plugin test checks that a warm recall stays under 50 ms.

**Prototype and plugin.** 0.10.0 ports the bench prototype "NA1" (§4.7), with the accent fix and the corrector (§4.11).
It drops every gear the measurements rejected: written maps, competition, episode brothers, cited raw passages,
designation, session first and time words (§5). The bench prototype differs in one respect: it filled a fixed
450-token block from 40 candidates per web, packed by budget, with no threshold. **All figures in §4 come from the
bench prototype**, not from the plugin module. The plugin module was checked against the prototype on the test sets, in
the prototype's own setting (40 candidates per web, a 450-token block): the same evidence-in-block rate on LoCoMo
(84.0 % and 84.0 %; 2 questions differ each way) and on LongMemEval (69.1 % and 69.1 %, identical question by question).
The candidate lists themselves differ where several items tie on score — the plugin breaks ties by a fixed order, the
prototype by the order of a Python set — and at the cut of the full-text search.

## 3. Method

**Benchmarks.** Two public benchmarks were used, both consolidated in earlier runs (`docs/09`, `docs/13`).

- **LoCoMo:** 10 long two-person conversations and 1,986 questions in five categories. Category 5 holds the traps:
  questions that attribute an event to the wrong person, where the right answer is "not mentioned".
- **LongMemEval, in its oracle setting:** 500 questions, each with only the sessions that hold its answer, between one
  "user" and an "assistant".

**Scale F (fused).** At scale F, all the conversations of a benchmark are fused into one memory, so every question
competes with all the others. Pages of the same node are merged, which mixes distractors with the right facts. LoCoMo
speakers who share a first name are kept apart.

| | Facts | Raw text | Citations resolved |
|---|---|---|---|
| LoCoMo F | 1,025 | 3,011 turns | 1,025 / 1,025 |
| LongMemEval F | 3,901 | 948 sessions | 3,901 / 3,901 |

All results below are at F.

**Sealed sets.** On 18/11, a tuning on about 120 messages had over-fitted. So on 21/11, before anything was built,
three sets were sealed:

| Set | LoCoMo | LongMemEval | Used for |
|---|---|---|---|
| Tuning | 304 questions, two conversations | 50 questions | every weight and every choice |
| Test | 196 questions, one conversation (the questions of earlier runs) | 100 questions (the earlier draw) | following each gear |
| Verdict | the test + 600 drawn (seed 2611) from the 1,486 outside it = 796 | the test + all 350 outside it = 450 | the decision |

The verdict draw was sealed again on 22/11 at 06:30, before any RAG answer was read. Its contenders and budget were
fixed in advance: NF1, S2, Rh and Rp at 450 tokens.

**The free evidence sensor.** Both benchmarks mark the replies that hold the answer (`evidence`, `has_answer`). The
sensor finds each one in the memory's raw text. An item covers it if it cites one of its lines (a fact) or contains it
(a raw turn). "**Evidence in the block**" is the share of questions whose block, packed exactly as the reader gets it,
covers at least one evidence reply. It costs no model and no tokens, and it is how N is tuned and each gear followed.

Three caveats apply:
- Questions without annotated evidence are left out (e.g. 6 of the 100 LongMemEval test questions).
- Evidence in the block is not a right answer: a raw turn can hold the evidence without what is needed to understand it
  ("yes, that one").
- A sensor defect fixed on 23/11 (a file prefix that also matched a twin conversation) changed one S2 question at 500
  conversations, and none for NA1 or Rp.

**Budgets.** B1 = 450 tokens, the 95th percentile of the 12-fact block of `memoire_chercher` (LoCoMo 364, LongMemEval
439). B2 = 1,350 tokens (3 × B1) and B3 = 4,500 (10 × B1). Tokens are counted with a fixed o200k tokenizer. Items are
packed whole, in the contender's order, never cut; an item too long for the room left is skipped.

**Reader and judge.** The reader is GPT-6.1 Terra at effort "high", with the benchmarks' own prompts unchanged (LoCoMo
QA, LongMemEval Chain-of-Note). The judge is Terra at effort "low", with Mem0's accuracy prompt for LoCoMo (category 5
scored by its abstention rule, no call) and LongMemEval's templates. Token counts are the real usage, and identical
calls are cached.

To check noise, the judge re-judged and the reader re-read 10 % of the questions; both were constant on 85–100 %. The
real cost was ≈ 970 tokens per LoCoMo question (reader 540, judge 410), so ≈ 180–210 k tokens per contender on the
LoCoMo test and ≈ 106 k on LongMemEval.

**These numbers are not comparable to public leaderboards.** The reader and judge are Terra, not GPT-4o-mini; the block
is 450 tokens; LongMemEval runs in its oracle setting. "J cat. 1-4" means LoCoMo accuracy without category 5 (the Mem0
protocol).

| Name | What it is | Stands for |
|---|---|---|
| S1 | `memoire_chercher` 0.9.15 (0.9.16 frozen, identical lists) | the search tool |
| S2 | the watch 0.9.16, search mode (`docs/21`) | the previous automatic recall |
| S2r | the watch re-weighted on the same tuning sets as N (coordinate ascent, criterion = evidence at 450) | control: architecture or tuning? |
| R | dense RAG: bge-m3 cosine over raw turns of two replies (LongMemEval's "round"), truncated at 512 tokens | the industry, no consolidation |
| Rh | hybrid RAG: BM25 (k1 1.2, b 0.75) + bge-m3 on the same turns, reciprocal rank fusion (k 60) | the strongest RAG here |
| Rp | bge-m3 over the consolidated facts | same memory as SEED: web or embeddings |
| N… | the new approach, gear by gear (§4.1) | the thesis |

All embeddings run bge-m3 on CPU, at the lowest priority, with no reranker.

**Equity rules, fixed in advance.**
- Every contender gets the same questions, reader, judge, token budget (embeddings included) and consolidated memories.
- The RAG is honest, hybrid included: no straw man.
- Writing costs are counted apart.
- N is tuned on the tuning sets only, and the watch was re-tuned on the same sets as a control (S2r).

**Statistics and the pre-registered criterion.** Paired McNemar tests compare contenders on the same questions: "a / b"
means a questions only the first got right, b only the second. Intervals are at 95 %.

The criterion was written before any measurement:
- **N wins** if it beats S2 *and* the RAG by at least 3 points on both benchmarks at F, gives the agent more useful
  memories at equal or better precision, and keeps p99 under 50 ms.
- **Tie** if it lands within ±3 points.
- **N loses** if the RAG or S2 beats it by more than 3 points on one benchmark.

A gear is kept if it improves things without degrading anything by more than 2 points. Each later choice (§4.11, §4.13)
had its own rule, written before its grid.

## 4. Results

### 4.1 The ladder of gears (evidence in the block, test, F)

| | LoCoMo B1 | LoCoMo B2 | LME B1 | LME B2 |
|---|---|---|---|---|
| S1 search 0.9.15 | 43.6 % | 44.7 % | 58.5 % | 61.7 % |
| S2 watch 0.9.16 | 40.4 % | 46.8 % | 58.5 % | 66.0 % |
| S2r watch re-tuned | 46.3 % | 51.6 % | 55.3 % | 63.8 % |
| **N1** cues + log-odds + rarity + threshold | **52.1 %** | **56.4 %** | 59.6 % | 62.8 % |
| N13 + competition | 52.1 % | 56.4 % | 59.6 % | 62.8 % |
| N134 + episode brothers | 52.7 % | 57.4 % | 57.4 % | 63.8 % |
| N1345 + cited raw passages | 51.1 % | 59.0 % | 53.2 % | 61.7 % |

N1, the log-odds combination, makes the jump on LoCoMo. The other gears add little:
- **Competition** fired only 3 times on LoCoMo, because a consolidated memory has few duplicates.
- **Brothers** (other facts of the same episode) change little, and not always for the better.
- **Passages** (the raw line a fact cites) take room at B1, costing 1 to 6 points against N1. They help a little at B2
  on LoCoMo (+1.6 over N134).

**The control S2r.** Re-tuned on the same sets, the watch rose from 41.8 to 45.6 % on tuning, yet N1 kept about 6
points over it on LoCoMo. So the gap comes partly from the architecture (log-odds, concept rarity, coverage), not only
from tuning. On LongMemEval, N1 ≈ S2 > S2r.

**Written maps (N2).** Here the consolidation model wrote nested maps and synonyms for 4,651 facts, at a cost of
342,649 + ≈ 30,000 tokens. They brought nothing: NF2 scored 61.2 % against NF1's 61.7 % on LoCoMo answers, and 48 %
against 49 % on LongMemEval. §4.4 shows why.

### 4.2 The raw web alone (Nb) and the two memories (NF1)

| Evidence in the block, test, F | LoCoMo B1 / B2 / B3 | LME B1 / B2 / B3 |
|---|---|---|
| Nb — raw web alone, no model at all | 72.9 / 85.1 / 92.0 % | 20.2 / 45.7 / 68.1 % |
| **NF1 — two memories** (N1 facts + Nb turns, merged by log-odds) | **80.9 / 92.6 / 96.8 %** | **63.8 / 71.3 / 80.9 %** |

NF1 beats each memory alone on both benchmarks. LongMemEval turns run to ≈ 600 tokens, so almost none fits in 450.

On tuning, single replies as the raw unit (NR1) lost to two-reply turns: a weighted 71.1 against 77.9. Warm NF1 recall
on the loaded server: on LoCoMo, p50 7 ms and p99 17 ms; on LongMemEval, p50 20 ms and p99 46 ms.

### 4.3 Answers (reader + judge), test, F, 450 tokens

| | LoCoMo (196) | J cat. 1-4 | traps cat. 5 | LME (100) | recall p50 (ms) | RAM peak | tokens / correct (LoCoMo) |
|---|---|---|---|---|---|---|---|
| S2 watch 0.9.16 | 43.9 % | 48.1 % | 11 / 40 | 45 % | 3–11 | 70–150 MB | 1,556 |
| S1 search 0.9.15 | 46.4 % | 50.6 % | 12 / 40 | 43 % | 4–11 | 60–150 MB | 1,429 |
| N1 web on facts | 48.5 % | 53.8 % | 11 / 40 | 44 % | 2–6 | 70–150 MB | 1,436 |
| Rp embeddings on facts | 49.0 % | 53.8 % | 12 / 40 | **51 %** | 282–290 | 2.4 GB | 1,421 |
| Nb raw web, no model | 55.1 % | 67.9 % | 2 / 40 | 22 % | 2–11 | 93–347 MB | 1,231 |
| R dense RAG on raw | 55.1 % | 67.3 % | 3 / 40 | 21 % | 274–310 | 2.5–2.8 GB | 1,245 |
| Rh hybrid RAG on raw | 56.6 % | 70.5 % | 1 / 40 | 22 % | 281–295 | 2.5–2.9 GB | 1,203 |
| NF2 two memories + written maps | 61.2 % | 76.3 % | — | 48 % | — | — | 1,115 |
| **NF1 two memories** | **61.7 %** | **77.6 %** | **0 / 40** | 49 % | **7–20** | **107–359 MB** | **1,109** |

| Paired against NF1 | LoCoMo | LongMemEval |
|---|---|---|
| Rh | 10 / 20 (p = 0.10) | 2 / 29 (p < 0.001) |
| R | 10 / 23 (p = 0.035) | — |
| Rp | 29 / 54 (p = 0.008) | 13 / 11 (p = 0.84) |
| S2 | 22 / 57 (p = 0.0001) | 8 / 12 (p = 0.50) |

N1 against S2 is 21 / 12 (p = 0.16): not significant. Against the watch, NF1's gain comes from LoCoMo categories 4
(62 / 73 against 27 / 73) and 1 (28 / 37 against 21 / 37).

### 4.4 Against embeddings, and the vocabulary gap (N0)

| Evidence in the block, test, F | LoCoMo B1 | LoCoMo B2 | LME B1 | LME B2 |
|---|---|---|---|---|
| R dense on raw | 63.3 % | 84.0 % | 19.1 % | 50.0 % |
| Rh hybrid on raw | 70.2 % | 84.0 % | 21.3 % | 57.4 % |
| Rp dense on facts | 48.4 % | 54.8 % | **68.1 %** | **73.4 %** |
| NF1 two memories, no model | **80.9 %** | **92.6 %** | 63.8 % | 71.3 % |

**N0, the vocabulary gap.** Here N1 and Rp are compared on the same facts and the same budget.

On LongMemEval, both found the evidence for 53 questions, only N1 for 3, and only the embeddings for 11. Ten of those 11
share at least two content words with the evidence reply. So the gap is ranking, not vocabulary: the embeddings order
facts that share the same words better.

On LoCoMo, only N1 found 20 and only the embeddings 13. Six of the 13 share no word at all with the evidence, so the
true vocabulary gap is 6 / 196 = 3 %. That is why written maps could hardly help.

The embeddings also cost far more:
- encoding the LongMemEval memory took 2 h 27 on 2 threads;
- a warm query took p50 ≈ 275–310 ms and p99 390–600 ms, mostly encoding the question on CPU;
- RAM was ≈ 3.5 GB, against 3–20 ms and 60–370 MB for the webs.

### 4.5 Time and energy on a quiet machine

Measured on a mini-PC (Intel Core i5-9500T, 6 cores, 16 GB) with public data only. Energy comes from the CPU package
RAPL counter (idle 0.26 W) and covers the whole run: building, then two queries per question for the determinism check.

| Scale F, LoCoMo · LongMemEval | recall p50 / max (ms) | whole run | energy | per question | RAM peak |
|---|---|---|---|---|---|
| S1 | 2.8 / 6.6 · 8.1 / 21 | 1.8 s · 4.2 s | 26 J · 68 J | 0.14 · 0.68 J | 60 · 145 MB |
| S2 | 2.8 / 6.3 · 7.9 / 20 | 1.6 s · 3.3 s | 26 J · 52 J | 0.13 · 0.52 J | 70 · 145 MB |
| N1 | 2.6 / 14 · 6.0 / 17 | 1.4 s · 2.5 s | 23 J · 41 J | 0.12 · 0.41 J | 67 · 145 MB |
| **NF1** | **4.8 / 9.2 · 14.5 / 33** | 2.5 s · 5.7 s | 40 J · 88 J | **0.20 · 0.88 J** | 105 · 357 MB |
| R / Rh / Rp, 1 thread | 200–237 / 300–563 | 53–86 s | 1,360–2,374 J | 12–14 J | 2.0–2.5 GB |
| R / Rh / Rp, 6 threads | 186–189 / 257–505 | 45–77 s | 1,234–2,419 J | 12 J | 2.0–2.5 GB |

Against the embeddings, NF1 is ≈ 40 times faster, with 15 to 60 times less energy and 6 to 20 times less RAM. Its p99
stays under 50 ms on a quiet machine; the 46–56 ms seen on the shared server came from load. More cores barely help
bge-m3, which encodes one question at a time.

### 4.6 The verdict (test + sealed verdict set, F, 450 tokens)

| | LoCoMo (796) | 95 % CI | J cat. 1-4 | traps cat. 5 | LME (450) | 95 % CI | reader tokens / correct (LoCoMo · LME) |
|---|---|---|---|---|---|---|---|
| **NF1 two memories** | **63.4 %** | 60.2–66.8 | **77.7 %** | 14 / 164 | **54.0 %** | 49.3–58.7 | **1,079** · 1,216 |
| Rh hybrid RAG (raw) | 58.2 % | 54.6–61.6 | 71.2 % | 13 / 164 | 23.1 % | 19.6–27.1 | 1,177 · 2,690 |
| Rp embeddings (facts) | 49.4 % | 46.1–52.9 | 52.2 % | 63 / 164 | 54.9 % | 50.4–59.3 | 1,409 · 1,221 |
| S2 watch 0.9.16 | 43.0 % | 39.8–46.5 | 45.6 % | 54 / 164 | 48.2 % | 43.6–52.9 | 1,603 · 1,377 |

The verdict cost ≈ 4 M tokens. Paired tests, NF1 against each:

| | LoCoMo | LongMemEval |
|---|---|---|
| S2 | 234 / 71 (p < 10⁻⁵) | 62 / 36 (p = 0.011) |
| Rh | 88 / 46 (p = 0.0004) | 148 / 9 (p < 10⁻⁵) |
| Rp | 207 / 95 (p < 10⁻⁵) | 47 / 51 (p = 0.76) |

**The benchmark part of the pre-registered criterion is met.** On LoCoMo, NF1 is 20.4 points above S2 and 5.2 above Rh.
On LongMemEval, it is 5.8 above S2 and 30.9 above Rh. Its p99 stays under 50 ms on a quiet machine.

Against embeddings over the same facts (Rp), NF1 is better on LoCoMo (+14.0) and level on LongMemEval (−0.9). The
real-life part of the criterion, more useful memories at equal precision for the agent, is not decided (§4.9).

### 4.7 NA1: an adaptive raw unit and feedback on the facts (all chosen on tuning)

**Why the raw text must be searched directly.** A fact cites the evidence reply for only 60.3 % of LoCoMo questions and
82.4 % of LongMemEval questions, yet NF1 already reaches 80.9 % on LoCoMo. Two ways of reaching the raw text through
the facts both failed at 450 tokens:
- **A pure cascade** (raw text reached only through citations) collapses: 33.9–40.2 % on LoCoMo and 56.2 % on
  LongMemEval, against 80.4 / 62.5 for the parallel search.
- **Letting a fact lift its cited turns** ("designation") gives nothing at +1 (weighted 77.1 against 77.9) and hurts at
  +2 (77.4 / 60.4) and +4 (61.5 / 56.2).

**What was kept.**
- **Adaptive raw unit.** Two replies if they fit in 600 characters, otherwise one. LoCoMo stays level (80.7 %) and
  LongMemEval rises to 66.7 % (from 62.5). It is free; any limit from 300 to 2,400 characters gives the same.
- **Feedback on the facts** (λ 1, 5 words). It reaches 82.4 / 68.8, a weighted 80.5 against 78.8. The same feedback on
  the raw text hurts (74–79 / 60–65), because conversations are wordy.
- **No offset between the webs.** Shifting the raw web's log-odds from −1 to +1 does best at 0 (80.5; −0.5 → 79.1;
  +0.5 → 79.6).

**Evidence in the block, NA1.** On the test: LoCoMo 83.0 % (NF1 80.9) and LongMemEval 70.2 % (NF1 63.8, Rp 68.1). On
the verdict sets: LoCoMo 81.9 (80.9) and LongMemEval 74.2 (68.8).

**NA1 answers on the 1,246 verdict questions:**

| | LoCoMo | LongMemEval |
|---|---|---|
| Accuracy | 63.1 % (59.8–66.5) | **58.9 %** (54.4–63.3) |
| J cat. 1-4 / traps | 77.5 % / 12 of 164 | — |
| Reader tokens per correct answer | 1,085 | **1,110** |
| Paired vs NF1 | 28 / 31 (p = 0.79) | **42 / 20 (p = 0.007)** |
| Paired vs Rh | 88 / 49 (p = 0.001) | 175 / 14 |
| Paired vs Rp | 204 / 95 | 69 / 51 (p = 0.12) |
| Paired vs S2 | 233 / 73 | 81 / 33 (p < 10⁻⁴) |

NA1 leads on both benchmarks. Its gain over NF1 is real on LongMemEval (+4.9, significant) and nil on LoCoMo (a tie).
Abstention does not move.

### 4.8 Abstention: the collapse with raw text, and the rule

**The collapse.** On the test's 40 traps, every contender that reads raw text collapses: Rh 1, Nb 2, R 3, NF1 0. Those
that read consolidated facts hold: S2 11, N1 11, S1 12, Rp 12. The verdict sets show the same, out of 164: Rp 63 and
S2 54, against NF1 14, Rh 13 and NA1 12.

So this is a property of raw text, not of NF1. With the raw lines in front of it, the reader answers instead of
abstaining. A consolidated fact says who said or did what, and that protects against misattribution — an argument
**for** consolidation.

**Discreet fixes, tried on tuning, did not help:**
- **Only the named person's lines.** Traps went from 1 / 71 (NF1) to 3 / 71 when filtered by turn and 8 / 71 when
  filtered by reply. The reply filter cost 5 points of evidence on the other questions.
- **An absence note.** Traps went from 0 to 2 / 14; other questions fell from 13 to 11 / 21.
- **Facts only when a detector fires.** Traps went from 0 to 4 / 14; other questions fell from 13 to 8 / 21.
- **A computed time note.** LongMemEval stayed at 29 / 50; LoCoMo category 2 went from 53 to 54 / 63.

**An explicit rule at the top of the block works** (§2). On tuning with NA1, it raised LoCoMo traps from 4 to 59 / 71.
It cost ordinary LoCoMo questions little: 75 down to 72 / 100. LongMemEval held at 36 / 50, and its abstention questions
went from 5 to 6 / 6.

At verdict scale, with the same NA1 blocks plus the rule on 796 + 450 questions:

| | Without the rule | With the rule | Paired |
|---|---|---|---|
| LoCoMo traps | 12 / 164 | **140 / 164** | — |
| LoCoMo categories 1-4 | 77.5 % | 71.4 % | 8 gained / 47 lost (p < 10⁻⁷) |
| LoCoMo overall | 63.1 % | 74.2 % | — |
| LongMemEval | 58.9 % | 57.3 % | 18 / 25 (p = 0.36, not significant) |
| LongMemEval abstention questions | 23 / 24 | 22 / 24 | — |

Three points need to be stated plainly:
- **The rule has a real cost:** about 6 points on ordinary LoCoMo questions.
- **Any system could adopt it.** It is a presentation gear, and the other contenders were not run with it, so these
  figures cannot be set beside §4.6.
- **0.10.0 ships it on,** because for an agent "I don't know" is worth more than an invented attribution. It can be
  switched off with `deux_memoires_regle: false`.

### 4.9 Real life: a quick run on the agent's messages

**The protocol.** It replays the agent's messages since 30/09, each against the memory as it was at that instant (git
snapshots). The raw web reads only turns older than 3 hours, never a retracted line, and takes neither the user's nor
the agent's name as a cue.

**Dry run.** 922 messages were replayed. On the 122 tuning messages:

| | Facts given | Silences | p99 latency |
|---|---|---|---|
| Watch | 243 | 53 | 110 ms (cold caches at each snapshot) |
| N1 | 244 | 73 | 24 ms |
| NF1 | 244 | 27 | — |

The raw web alone ran at 23 ms p99.

**The quick run.** It used the 43 fresh messages of 19–22/11 and cost ≈ 550 k tokens (judge 69 k, answers 481 k).

One deviation from the sealed protocol must be stated. The sealed rule admitted only messages after 21/11 23:59; the
cut-off was moved earlier, after the fact, to 18/11 23:59. The last message used by any tuning or judging dates from
18/11, which was checked by file dates without reading any content.

| Variant | Useful / given (blind judge) | Items per message | Mean answer score |
|---|---|---|---|
| 0.9.15 | 16 / 54 (30 %) | — | 3.40 |
| watch 0.9.16 | 23 / 101 (23 %) | 2.3 | 3.49 |
| N1 | 23 / 110 (21 %) | — | — |
| NF1 | **31** / 145 (21 %) | 3.4 | 3.57 |
| NA1 | 17 / 124 (14 %) | 2.9 | **3.60** |
| no memory | — | — | 3.34 |

**Answers.** NA1 took 13 first places and made 16 inventions, against 19–21 for the others. It won its duels 28–15
against 0.9.15, 24–19 against the watch, 22–21 against NF1 and 28–15 against no memory. The watch beat 0.9.15 22–21.

**What the run shows.**
- **The threshold did not transfer.** It was set to match the watch's volume, yet NF1 and NA1 gave more items than the
  watch on these messages.
- **NA1 gives the best and least inventive answers, yet the memory judge counts the fewest useful items for it.** Its
  raw extracts help answering without being "useful" one by one.
- **The real-life criterion is not met on this run.** It shows more useful memories (NF1 31 against 23), but at lower
  precision (21 % against 23 %; NA1 14 %).

This is a trend only. 43 messages settle nothing, and the abstention rule was not in this run. The 100-message run is
pending.

### 4.10 Interference and the damaged question (23/11, evidence sensor, no tokens)

These are two classic tests from the associative-memory literature.

**Test 1, interference: the same questions asked of ever bigger memories.**
- **LongMemEval** (test, 100 questions): 10 groups of 10 conversations (seed 42), each merged with 0, 40 or 190 others
  drawn at random. This gives nested memories of 1, 10, 50, 200 and 500 conversations; "1" is the conversation's memory
  alone.
- **LoCoMo** (test, 196 questions): the conversation alone, the 10 conversations, then the 10 plus the 500 LongMemEval
  conversations.

The rebuilt 500-conversation fusion is byte-identical to the F memory, and NA1 answers the same on it, question by
question. Latencies were measured under load (two lanes on 2 cores, lowest priority).

| LongMemEval, evidence at 450 | 1 | 10 | 50 | 200 | 500 | lost / gained | p50 / p95 ms, small → large | RAM (MB) |
|---|---|---|---|---|---|---|---|---|
| **NA1** | **93.6** | **89.4** | **80.9** | **78.7** | **70.2** | 23 / 1 (p < 10⁻⁵) | 1 / 3 → 27 / 52 | 151 → 348 |
| Rp embeddings on facts | 80.9 | 80.9 | 74.5 | 72.3 | 68.1 | 12 / 0 (p = 0.0005) | 315 / 470 → 310 / 474 | 2,408 → 2,424 |
| S2 watch 0.9.16 | 72.3 | 72.3 | 69.1 | 63.8 | 58.5 | 13 / 0 (p = 0.0002) | 1 / 1 → 9 / 18 | 150 → 150 |
| Rh hybrid RAG on raw | 33.0 | 34.0 | 31.9 | 27.7 | 21.3 | 11 / 0 (p = 0.001) | 304 / 470 → 328 / 501 | 2,413 → 2,880 |

| LoCoMo, evidence at 450 | alone | 10 | 10 + 500 LME | lost / gained | p50 / p95 ms | RAM (MB) |
|---|---|---|---|---|---|---|
| **NA1** | **80.3** | **82.4** | **79.8** | 7 / 6 (p = 1) | 3 / 4 → 22 / 42 | 76 → 368 |
| Rh | 70.2 | 70.2 | 70.7 | 6 / 7 (p = 1) | 278 / 334 → 300 / 354 | 2,472 → 2,809 |
| Rp | 48.4 | 48.4 | 47.9 | 1 / 0 (p = 1) | 288 / 340 → 287 / 359 | 2,395 → 2,450 |
| S2 | 50.0 | 45.2 | 35.1 | 28 / 0 (p < 10⁻⁸) | 1 / 2 → 14 / 21 | 53 → 156 |

NA1 stays first or level at every size, but on LongMemEval it loses almost twice as much as the embeddings (−23 points
against −13). A bigger budget does not help: at 1,350 tokens NA1 still falls from 97.9 to 75.5. So the evidence is
outranked, not merely cut off by the budget.

LoCoMo stays stable, because first names keep its conversations apart. LongMemEval's distractors come from "the same
person", a single "user" with everyday subjects. Since the agent's memory is mostly one user's, the LongMemEval case is
the one that matters.

**Test 2, the damaged question (F).** Typos hit 10, 25 or 50 % of the words of 4 letters or more: a swap, a drop, a
doubled letter or a neighbouring QWERTY key. Separately, 20 or 40 % of the words are dropped. The damage is
deterministic per question, so every contender gets the same question.

| Evidence at 450 (NA1 / S2 / Rp / Rh) | clean | typos 10 % | 25 % | 50 % | words lost 20 % | 40 % |
|---|---|---|---|---|---|---|
| LoCoMo | 82.4 / 45.2 / 48.4 / 70.2 | 76.6 / 44.1 / 47.9 / 67.0 | 80.3 / 44.1 / 47.9 / 66.5 | 63.8 / 41.0 / 46.8 / 52.7 | 76.6 / 43.1 / 46.8 / 61.7 | 65.4 / 34.6 / 38.8 / 47.9 |
| LongMemEval | 70.2 / 58.5 / 68.1 / 21.3 | 64.9 / 57.4 / 67.0 / 19.1 | 58.5 / 55.3 / 64.9 / 19.1 | 59.6 / 52.1 / 66.0 / 14.9 | 67.0 / 55.3 / 67.0 / 19.1 | 62.8 / 47.9 / 56.4 / 14.9 |

On LoCoMo, NA1 leads everywhere: its worst case is 63.8, against 52.7 for Rh and 46.8 for Rp (p < 0.006). It still
loses a lot in absolute terms: 18.6 points at 50 % typos and 17.0 at 40 % lost words.

On LongMemEval, typos let the embeddings pull ahead:
- at 25 % typos, NA1 58.5 against Rp 64.9 (11 / 17, p = 0.35);
- at 50 % typos, 59.6 against 66.0 (8 / 14, p = 0.29).

Neither gap is significant, but both point the same way: typos are the weak point of lexical recall. Lost words are
not (at 40 %, NA1 62.8 against Rp 56.4). The damage levels are not nested (on LoCoMo, 10 % typos cost 5.8 points but
25 % only 2.1), so allow about ±3 points of noise per level.

### 4.11 Accents, determinism and the corrector

**Accents.** Reading the code showed that the raw side of NA1 did not fold accents, while the facts side did. The
English benchmarks could not see the defect. The fix uses the same normalisation on both sides. Evidence on the test at
F is unchanged: LoCoMo 82.4 / 93.1, LongMemEval 70.2 / 75.5 (at 450 / 1,350).

**Determinism across processes.** Two runs of the same code on byte-identical memories gave different lists for 16 / 196
LoCoMo and 6 / 100 LongMemEval questions. The differences were at ranks 27 and below, and no evidence was affected. The
likely cause is Python's random hash order breaking ties; 0.10.0 breaks them by a fixed order.

**The corrector.** Its selection rule was fixed before the grid: the best gain on damaged questions, at a cost of at most
0.5 point on clean ones. The grid ran on tuning at 450 tokens (LoCoMo 304 questions and LongMemEval 50, weighted).

| Corrector variant | Clean | Damaged | Result |
|---|---|---|---|
| none | 80.5 | 67.7 | — |
| both webs, ≥ 4 letters | 79.7 | 78.3 | rejected (clean −0.8) |
| **both webs, ≥ 5 letters** | **80.3** | **77.7** | **kept** |
| both webs, ≥ 6 letters | 80.3 | 75.8 | — |
| raw web only | 80.3 | 76.7 | — |
| memories web only | 79.9 | 70.4 | — |

At 50 % typos on tuning, it lifted LoCoMo from 60.8 to 77.1 and LongMemEval from 50.0 to 66.7.

It was then confirmed on the test. The base there is NA1 with accents, re-measured after the sensor fix (§3), so it can
differ from §4.10 by up to 0.6 point on damaged LoCoMo questions.

| Test, evidence at 450 | clean | typos 10 % | typos 25 % | typos 50 % |
|---|---|---|---|---|
| LoCoMo base → corrector | 82.4 → 84.0 (3 / 0, n.s.) | 77.1 → 80.9 (8 / 1, p = 0.04) | 80.9 → 83.0 (n.s.) | **63.3 → 77.7 (28 / 1, p ≈ 10⁻⁷)** |
| LME base → corrector | 70.2 → 69.1 (0 / 1) | 64.9 → 69.1 | **58.5 → 66.0 (8 / 1, p = 0.04)** | 59.6 → 66.0 (12 / 6, n.s.) |

Overall, clean questions went from 78.3 to 79.0 and damaged ones from 69.3 to 73.2. Lost words were unchanged, as
expected. Against Rp, the typo gap on LongMemEval is closed: 66.0 against 64.9 and 66.0 (13 / 12 and 13 / 13).

Clean questions get 0.10–0.17 corrections each on the test (0.2–0.4 on tuning). One risk was seen in testing: a word
absent from the memory can be "corrected" into another ("Paris" into "pairs").

### 4.12 Diagnosing the interference

This was a read-only analysis: no model, no tokens. The evidence sensor was rebuilt and matched the original on 1,410 /
1,410 verdicts. The analysis covers the 94 LongMemEval test questions that have evidence.

**What was lost.** Between 1 and 500 conversations, NA1 lost 23 questions and gained 1. The first loss came at 10
conversations for 6 questions, at 50 for 7, at 200 for 3 and at 500 for 7.

| Question type | Lost / found at 1 |
|---|---|
| preference | 6 / 9 |
| temporal | 8 / 24 |
| multi-session | 6 / 21 |
| user | 2 / 14 |
| knowledge update | 1 / 12 |
| assistant | 0 / 8 |

At 500 conversations, none of the 23 blocks holds a single item from the right conversation. They hold 213 items from
117 other conversations, none dominant. The evidence had left the 80-item list in 11 cases, sat under the cut in 11,
and was skipped as too long in 1.

**The evidence does not sink; the bar rises.** The median score of the last item to enter the block goes from −8.18 at
1 conversation to −3.94 at 500. Where the evidence item was found again at 500 (8 of the 23), its score had risen in 7.

Rarity does not collapse either: every word's IDF goes up. What grows is the number of competitors that carry the same
words. For lost questions, the evidence's words appear in a median of 165 files of other conversations, against 117 for
the questions kept. Typical words in lost questions are frame or request words found everywhere: "tips" appears in 718
of 948 files, "recommend" in 695, "suggest" in 541.

**How the 213 distractors win:**
- 105 share a keyword with the evidence;
- 81 win only on question words the evidence lacks ("ago", "two", "weeks", "suggest", "latest");
- 27 share no content word with the question at all.

On questions with a relative time, 50 of 88 distractors also carry a time expression.

**Few shared words make a question vulnerable.** When the evidence shares at most one content word with the question,
NA1 lost 10 questions of 13. When it shares four or more, it lost 3 of 44.

**The embeddings show the same pattern.** Rp lost 12 questions, 8 of them in common with NA1, and gained none. Its
evidence cosine is identical at 1 and 500 conversations, so its losses are pure competition. Its distractors come from
different conversations than NA1's (Jaccard 0.08).

**This is not a sensor artefact.** The 500 conversations hold 52 pairs of near-twins, but for a lost question the twin
copy of the evidence is never in the block (0 / 23).

Four questions remain open:
- "same person" (not testable inside LongMemEval);
- "same theme" (distractors were classed by words only);
- which cue pushes each distractor up;
- the true rank of the 11 evidence items that left the list.

### 4.13 Two ideas rejected on the test set

Both target interference. Both stay off in the prototype, and neither is in 0.10.0.

**Time words.** The expressions read by the time window ("two weeks ago") are taken out of the searched words, so they
serve only to set dates.

**Session first** (weight w, recruits R). Each raw session gets the share of the question it covers on its own; a fact
gets the share covered by the sessions it cites. Every item gains w × that share. The items of the R best sessions that
share a word with the question join the candidates. This is the "region first" idea of nested maps, at last somewhere
it can be measured.

**The rule, fixed before the grid.** Tuning, F, clean questions, evidence at 450. The score is the plain mean of LoCoMo
and LongMemEval. A variant is rejected if one benchmark loses more than 1 point against the base, and ties go to the
simpler variant. The base is NA1 with accents and the corrector.

**The grid** (LongMemEval 48 questions / LoCoMo 301):

| Variant | LongMemEval / LoCoMo |
|---|---|
| base | 68.8 / 82.1 |
| time words | 68.8 / 81.4 |
| session w 0.5 | 70.8 / 81.7 |
| **session w 1** | **72.9 / 82.1** |
| session w 2 | 70.8 / 80.7–81.1 |
| session w 4 | 70.8 / 79.4 |

Time words plus session never beat session alone, and recruits (R 5) had no effect. So the rule picked session w 1
without recruits. Caveat: its +4.1 on LongMemEval is 2 questions out of 48.

| Test, evidence at 450 | LME 1 | 10 | 50 | 200 | 500 | lost / gained | LoCoMo alone | 10 | 10 + 500 |
|---|---|---|---|---|---|---|---|---|---|
| base (NA1 + accents + corrector) | 93.6 | 88.3 | 80.9 | 78.7 | 69.1 | 24 / 1 | 80.3 | 84.0 | 79.3 |
| session first | 93.6 | 87.2 | 83.0 | 77.7 | 68.1 | 24 / 0 | 80.3 | 84.0 | 80.3 |
| time words | 93.6 | 89.4 | 80.9 | 78.7 | 68.1 | — | 78.7 | 81.9 | 77.1 |

**On the test, it was not confirmed at any memory size.** Session first against base, size by size: 0 / 0, 1 / 2,
3 / 1, 1 / 2, 1 / 2. Nothing is significant, and the interference curve does not move. Time words are slightly worse on
LoCoMo (1 / 5).

**Both ideas are rejected.** The +4.1 on tuning was noise. Latency was unchanged (≈ 24 ms p50, 43–50 ms p95 at 500).

**What remains.** The hard core of the diagnosis is evidence that shares at most one word with the question. Word or
session heuristics do not recover it, and the embeddings lose there too (−12). The remaining lever is meaning: what
consolidation writes, such as concepts and wordings close to future questions. That is still to be measured.

## 5. What did not work (kept for the record)

| Idea | Result |
|---|---|
| Nested maps and synonyms written by the consolidation model (N2) | ≈ 370 k tokens of writing, nothing measurable (61.2 % vs 61.7 %); the vocabulary gap is only ≈ 3 % |
| Competition (N3) | fired 3 times |
| Episode brothers (N4) | small, mixed changes |
| Cited raw passages (N5) | cost room at 450 tokens (−1 to −6 points) |
| Pure cascade to the raw text | collapses (33.9–40.2 % vs 80.4 % on LoCoMo tuning) |
| "Designation" of cited turns | nothing at +1, harmful when stronger |
| Single replies as the raw unit | lost to two-reply turns; replaced by the adaptive unit |
| Feedback on the raw text | hurts |
| Balance offset between the two webs | best at zero |
| Absence note, "facts only" detector, computed time note | no effect |
| Only the named person's lines | barely helps; −5 points of evidence elsewhere |
| Session first, time words | not confirmed on the test (§4.13) |

## 6. Limits

**Benchmarks are not life.** Benchmarks are magnifying glasses for defects; the value has to be proven, and measured, on
the agent itself. LongMemEval's conversations are not the agent's. Its oracle setting holds only the sessions with the
answer, and the real haystack (≈ 48 sessions per question) was not tested. These numbers are not comparable to public
leaderboards (§3). N was tuned on tuning sets of the same benchmarks: sealed and never the test, but the same kind of
data.

**The weights come from English benchmark conversations.** There, the work-rule cue comes out negative, while rules
matter on the agent's memory. Only the threshold was set on the agent's messages, and it did not transfer to fresh ones
(§4.9).

**The real-life validation is pending.** Phase 2, with 100 fresh messages, has not run. The 43-message run is a trend,
measured without the abstention rule.

**Interference is not solved.** On LongMemEval, from 1 to 500 conversations, NA1 loses 23.4 points at 450 tokens
(93.6 → 70.2) and 22.4 at 1,350 (97.9 → 75.5). Three times the budget leaves the slope unchanged, and two heuristics
failed (§4.13).

**The agent is at about one fifth of the "500" size.** Its memory holds 184 raw sessions (2.7 MB) and 1,752 lines of
facts. The 500 LongMemEval conversations hold 948 sessions (15 MB) and 8,402 lines. That places the agent between the
50 and 200 points of the curve (≈ 79–81 % evidence on this benchmark). At its current pace, 2.7 MB in two months, it
would reach "500" in about a year.

**Forgetting is not switched on yet** (`oubli.py`, since 0.9.3). It is one natural answer to a memory that only grows,
and it is not measured here.

**Other limits.**
- **The typos are synthetic:** English, QWERTY, never on the first letter.
- **The corrector's effect on abstention is not measured.** A wrong correction ("Paris" into "pairs") could mislead a
  reader. The evidence sensor cannot see this, and measuring it by reading costs tokens.
- **Abstention rests on a presentation rule** that costs ≈ 6 points on ordinary LoCoMo questions (§4.8). Without it,
  every contender that reads raw text answers the traps.
- **Both voices come back.** Consolidation keeps the agent's own statements only when they are confirmed, but the raw
  web returns both voices. The agent's lines are marked "(you)"; their effect on invented answers needs watching.
- **The figures are the prototype's, not the plugin's** (§2); the plugin gives the same evidence rate on the test sets.
  Latencies on the shared server were taken under load; the quiet-machine figures are in §4.5.

## 7. Reproduce

The bench scripts are in `banc/eval/` (see its `README.md`), the shared helpers in `banc/harnais/`.

| Script | Role |
|---|---|
| `capteurs.py` | shared sensors: fixed o200k tokenizer, time per stage, RAM, manifests |
| `preuves.py` | the free evidence sensor |
| `n.py` | the prototype of the two webs, every gear and every rejected option |
| `fournir_n.py`, `fournir_seed.py`, `fournir_rag.py` | ranked lists for N, S1 / S2 and R / Rh / Rp |
| `paqueter.py` | the common token budget |
| `lire_juger.py` | the common reader and judge, with real token usage, a cache and the 10 % noise check |
| `rapport.py` | the automatic report |
| `bruit.py`, `echelle.py`, `fusion_eval.py` | damaged questions, memory sizes and nested fusions |
| `regler_n.py`, `regler_nb.py`, `regler_s2.py` | the fits, on the tuning sets only |

Each run's manifest records the fingerprints of the sealed sets (`7bc4a541…`), the verdict seal (`c48f8fd9…`) and the
tokenizer (`43a3ad46…`). The published `scelle.json` leaves out the section about the agent's real messages, so its own
hash differs from the one in the manifests. LoCoMo and LongMemEval are public. The consolidated benchmark memories, the runs, and anything
from the agent's own memory or messages are not published.
