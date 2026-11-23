# EXIA SEED

**A long-term memory for AI agents, built on Karpathy's *LLM Wiki* — with an associative graph instead of vector search.**

No embedding model. No vector database. Every memory is a sentence in a markdown page that cites the exact line of
conversation it comes from; every retrieval score can be recomputed by hand, and every search replays identically.

EXIA SEED runs every day as the memory of **Nexa**, the personal assistant of a French craftsman, since September 2026.
This repository is its working notebook: the code, the tests, the benchmarks, and the full engineering log — failures
included.

> Names of people, companies and places, and private information, are **fictitious** in this public version — replaced
> for the purpose of the demonstration, but based on real cases (`docs/00-AVERTISSEMENT.md`).

---

## Why

Andrej Karpathy's [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) (April 2026) proposes
that an agent should *compile* what it learns into a maintained wiki — immutable raw sources, a wiki written by the
model, a schema — instead of re-searching raw chunks on every question. At scale, the usual answer is to add vector
search on top.

EXIA SEED asks a different question: **can the wiki find its own way without embeddings?**

Its answer is an associative graph over the wiki pages — a fuzzy cognitive map (Kosko, 1986) — where a question
activates the pages it names, activation spreads along links that were *lived together* in conversation, and a small
scoring primitive (`cab_pull`, a confidence-weighted linear pull toward a target) ranks the facts. The model reads the
wiki like a person reads a notebook; the graph points it to the right pages.

## How it works

```
conversation ──► raw/ (append-only, hash-chained, secrets masked)
                    │  nightly consolidation by an LLM, one fact = one cited sentence
                    ▼
               pages/<subject>.md ──► INDEX.md      (Karpathy's wiki layer)
                    │  co-occurrence + naming + shared concepts
                    ▼
               graph/ (sparse, weighted, every edge keeps its evidence)
                    │
          ┌─────────┴──────────┐
   memory_search (tool)    automatic recall (each message)
   full text opens the      the subjects a message touches
   door, the graph ranks    come back on their own, as data
```

- **Consolidation with a citation check.** The LLM proposes facts; a deterministic checker refuses any number, date or
  proper noun absent from the cited lines, and anything that rests only on the agent's own words (the agent must not
  persuade itself). It is a lexical check: a false statement built from the source's own words can still pass — a
  known blind spot (`docs/04` §5.3).
- **Associative retrieval, no embeddings.** BM25 opens the door; spreading activation on the sparse graph ranks the
  candidates and adds associated subjects; the facts that *create* a link are offered as leads.
- **Automatic recall.** On each message, the subjects it touches surface on their own (phase 2), as data, never as
  instructions.
- **Voice, both ways.** The user's voice messages are transcribed locally into the raw log, and the assistant's spoken
  replies are written there in clear text — both feed the memory like typed messages (`docs/12` §15).
- **Deterministic and auditable.** Same memory, same question → same result, byte for byte (tested across hash seeds).
- **Small.** On a fused memory of 2,834 graph nodes and 3,901 facts: 11 ms median per search, 18 ms p95, 123 MB for
  the whole process. A bge-m3 embedding search on the same facts: 315 ms median, 496 ms p95 — and the model alone
  needs 2.6 GB of RAM (measured on LoCoMo).

It ships as a `MemoryProvider` plugin for [Hermès Agent](https://github.com/NousResearch/hermes-agent), with French and
English language masks.

## Real use first

The value of a memory shows over months of a real relationship, not in a benchmark. What we measure on Nexa:

- in daily use since **22 September 2026**: 583 cited facts in 64 subject pages after five weeks;
- **automatic recall** live since 18 October: on 100 messages up to 28 October, 37 received memories (≈ 230 tokens on average, `docs/11` §8); e.g.
  asked *"do you remember last week's shopping list?"*, the subject came back on its own and the assistant restored
  the 23 items of 15 October;
- **voice**: on 28 October a voice message ("thanks for the reminder, I have the document for the insurer")
  and the assistant's spoken reply were written to the raw log; that night's consolidation turned them into two cited
  facts;
- **28 October**: her whole history (126 daily batches) re-consolidated twice with her production model, old vs new
  consolidation rule, on copies: 422 → 732 facts, 54 % → 71 % of the user's messages cited by at least one fact,
  **22 → 36 correct answers out of 80** questions drawn from her real messages (16 gained / 2 lost, McNemar p = 0.001).

## 0.10.0 — two memories, one web

Is consolidation necessary, or can recall read the raw conversation? Both, it turns out. Since 0.10.0 the automatic
recall can read **the consolidated memories and the raw log together** (`rappel_moteur: deux_memoires`; the default
stays `ancien`, so installing it changes nothing, and switching back is the rollback). Each memory and each raw turn
gets the sum of its cues in log-odds — rarity, coverage of the message, named page or person, concept, time window —
with weights fitted on benchmark tuning sets only; the two lists are merged, at most 10 items reach the agent, with an
**abstention rule** on top of the block and the agent's own past words marked as such. No model at recall time, no
embeddings (`docs/22`).

Evaluated on LoCoMo and LongMemEval with sealed tuning / test / verdict sets and a free evidence sensor, on fused
memories, with the same 450-token block for every engine (reader GPT-6.1 Terra « high », judge Terra « low » —
**not comparable to public leaderboards**):

| verdict sets, fused memory | LoCoMo (796 q) | LongMemEval (450 q) | recall latency | RAM |
|---|---|---|---|---|
| **two memories (0.10.0)** | **63.1 %** | **58.9 %** | 5–30 ms | ≈ 350 MB |
| hybrid RAG on raw turns (BM25 + bge-m3) | 58.2 % | 23.1 % | ≈ 300 ms | 2.5–2.9 GB |
| bge-m3 on the consolidated memories | 49.4 % | 54.9 % | ≈ 300 ms | ≈ 2.4 GB |
| the watch (0.9.16) | 43.0 % | 48.2 % | 3–11 ms | 70–150 MB |

Two memories vs hybrid RAG on LoCoMo: p = 0.001; vs embeddings on LongMemEval: not significant. With the abstention
rule, the questions built as traps are answered « not mentioned » 140 times out of 164 (12 without it), at a cost of
about 6 points on ordinary LoCoMo questions. A corrector drawn from the memory itself absorbs typos (50 % misspelt
words: 63.3 → 77.7 % evidence recall on LoCoMo). **Not solved**: interference as one person's memory grows — the
evidence reaches the block for 93.6 % of the questions with one conversation in memory, 69.1 % with 500; two candidate
fixes were rejected on the test set. 0.10.0 is **not yet switched on** for the agent: its real-life validation comes
first.

## Benchmarks — as defect magnifiers, with their limits

Benchmarks are useful to find defects and to compare retrieval engines on equal footing. (The section above uses the
protocol of `docs/22`; the results below, from `docs/09` and `docs/13`, use another reader and judge.) Each protocol below was
**written before the measurement** (hypotheses and thresholds included) and every result is reported, including the
failures. Engines compared on the **same consolidated memory**: A = EXIA SEED, B = bge-m3 embeddings, C = BM25.

**LongMemEval** (Wu et al., ICLR 2025), *oracle* variant, the 500 per-question histories **fused into one memory**,
official reading and judging prompts (verbatim), gpt-4o-mini judge:

| fused memory, 500 questions | EXIA SEED | embeddings | full text |
|---|---|---|---|
| blind run (no tuning, questions never seen) | 34.2 % | 35.4 % | 31.6 % |
| + exhaustive consolidation (confirmed on 300 held-out questions) | 44.4 % | 46.6 % | 40.2 % |
| + gpt-4.1-mini as reader | **52.4 %** | **51.6 %** | — |
| abstention (unanswerable questions), same run | **83 %** | 67 % | — |

The differences between A and B are not statistically significant: **EXIA SEED matches embedding retrieval** without
an embedding model, loses less when the memory grows (−10 vs −15 points from per-question to fused memory), and
abstains more often when it should. With the gpt-4o-mini reader, our pre-registered threshold (A ≥ B − 2 points) is
missed by 0.2 point on the exhaustive row — reported as a failure. The ceiling is the memory itself: with the full
conversation in context, gpt-4.1-mini reaches 89 % (gpt-4o-mini: 77 %).

**LoCoMo** (Maharana et al., ACL 2024), 10 conversations fused, Mem0 judging protocol: 36.8 % vs 38.3 % for embeddings
on the 8 verification conversations (two clean held-out conversations: 121 vs 122 correct). Six of those eight
conversations were used for diagnosis — reported as such.

**What these numbers are not**: a leaderboard entry. Our LongMemEval setting (oracle, fused) differs from the usual
*S* setting and our judge is gpt-4o-mini; scores published by memory vendors use larger models and are, for most of
them, reported by their own authors.

## Which model consolidates — a small model is enough

Consolidation (turning the raw log into cited facts) is the only step that calls a model. Bench 17 compares
consolidators on six real days of the author's agent memory that no prompt was tuned on, same questions, reader and
judge (`docs/17`, `docs/20`):

| six unseen days | correct answers | coverage of the user's messages | cost per million raw tokens |
|---|---|---|---|
| GPT-6 Astra, production prompt (reference) | 65.3 % | 84.1 % | ≈ $42 |
| GPT-6.1 Terra, adapted prompt | 73.4 % | 85.2 % | ≈ $3.3 |
| **GPT-6 Luna, effort low, prompt written for it, 10,000-token lots** | **75.8 %** | 83.5 % | **≈ $0.46** |
| Claude Haiku 5.5, same prompt, effort low | 71.8 % | 89.6 % | ≈ $1.5 |

What made the difference was the prompt (one absolute rule — every name and number word for word from the cited lines —
and working message by message), then small lots; the same prompt transfers from one lab to the other. Showing the model
only the pages the search brings back, message by message, keeps the cost independent of the memory's size (`docs/19`),
and the memory forgets what it no longer uses, under explicit conditions (`docs/18`).

## Repository layout

```
plugin/exia_seed/   the plugin (consolidation, graph, sparse engine, retrieval, recall, language masks)
tests/              34 test suites, each run in a disposable container with Hermès' real plugin loader
banc/               the benchmarks: LoCoMo, LongMemEval, real-memory benches, banc/eval (docs/22) — scripts only, no private data
docs/               the engineering log, step by step (French up to docs/17, English from docs/18) — decisions,
                    measurements, mistakes
```

Run the tests: `sh tests/banc.sh` (Docker; uses the Hermès image). Benchmark scripts and their exact protocols are in
`docs/09` (LoCoMo) and `docs/13` (LongMemEval).

## Limitations

- Consolidation needs a capable model: on real, messy conversations (an agent that acts, one-word confirmations, tool
  output) a small model writes too few facts. Retrieval needs no model at all.
- Validated on conversational memory, in French and English; not yet on sensor, mission or maintenance logs.
- Python; the sparse engine is O(nodes + edges) but has not been measured beyond a few thousand subjects.
- The engineering log is in French up to `docs/17`, in English from `docs/18`.
- Recall degrades as one person's memory grows (`docs/22`): forgetting (`docs/18`) is meant to bound it, not yet measured.

## Lineage and credits

- Andrej Karpathy — *LLM Wiki* (2026), the base layer; rohitg00 — *LLM Wiki v2*.
- Bart Kosko — fuzzy cognitive maps (1986); Vannevar Bush — *As We May Think* (1945); Hermann Ebbinghaus — the
  forgetting curve (1885). Full list in `docs/SOURCES.md`.
- The propagation engine (`plugin/exia_seed/moteur/fcm.py`) comes unchanged from EXIA GHOST, the author's earlier
  cognitive architecture.

## Author

**Francis Babin** — idea, architecture, decisions. Engineering, benchmarks and documentation in partnership with
Claude (Anthropic) through Claude Code.

## License

Apache License 2.0 — see `LICENSE`.
