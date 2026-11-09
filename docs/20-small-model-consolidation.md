# 20 — Consolidating with a small model: GPT-6 Luna and Claude Haiku 5.5 (November 2026)

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

*Continues `docs/17` and `docs/19`. Same bench as `docs/17` (bench 17): six real days of the agent's memory per panel,
the same questions, the same reader and judge (Terra), the same thresholds — **Q1** correct answers ≥ reference − 5
points, **Q2** coverage ≥ reference − 5, **Q4** no lot lost; the reference is GPT-6 Astra with the production prompt.
The first panel served to tune prompts; **the second panel was never seen by any prompt and is the one that decides.***

## 1. Why

A consolidator ten times cheaper than Terra (Luna: $0.10 / $0.50 per million input / output tokens, against $1 / $5)
changes what a memory costs to keep. In bench 17, with the production prompt, Luna was far behind (33.1 % correct,
31.6 % coverage); it had never been tried with a prompt written for it.

## 2. Step 1 — Luna with Terra's adapted prompt

Luna, effort "low", Terra's adapted prompt as is, first panel: **57.0 % / 57.9 %** — a big jump from 33 %, but short of
the thresholds by 0.7 and 7 points. On the first pass it already ties Astra question by question (8 against 8).

Where it falls short, compared with Terra fact by fact on the same lots: the **middle** of long days (coverage 46 %
against 82 %), **short** messages (38 % against 62 %), and a whole day when it writes the conversation date into facts
(rejected by the citation check: 36 % against 93 %). Its rejections (52 per pass against 16 for Astra): the day of the
month added to a fact, or the page's name added although the cited line does not say it. The citation check does its job;
**the prompt had to change, not the check.**

## 3. Lot size: consolidating continuously in small lots

With a cheap consolidator one can consolidate continuously, in small lots, while raw text keeps being written: the
memory is fresh during the day, the load is smoothed, and a heavy professional day is not consolidated in one block.
Same model and prompt; each day's pending lots split at message boundaries into chunks of at most K tokens
(`banc/modeles/decouper.py`), one pass taking at most K:

| Luna, Terra's prompt, first panel | Correct | Coverage | Facts kept | Rejections | Passes | Time per pass | Cost per pass |
|---|---|---|---|---|---|---|---|
| Lots up to 40,000 (a day at once) | 57.0 % ✗ | 57.9 % ✗ | 96 | 53 | 6 | — | $0.02 |
| **Lots of 10,000** | **61.3 % ✓** | 63.6 % ✗ | 136 | 56 | 11 | 27 s | $0.03 |
| Lots of 6,000 | 57.0 % ✗ | 58.3 % ✗ | 115 | 66 | 12 | 24 s | $0.03 |
| Lots of 3,000 | 59.2 % ✓ | 63.6 % ✗ | 137 | 60 | 19 | 20 s | $0.03 |

Small lots help (+4 points of answers, +6 of coverage at 10,000); 6,000 below both 3,000 and 10,000 reflects Luna's
pass-to-pass variability more than a size effect. **10,000 kept.**

## 4. Step 2 — a prompt written for Luna

`banc/modeles/consigne_luna.txt` = Terra's adapted prompt plus an **ABSOLUTE RULE** at the top (every proper noun and
number in a fact must appear word for word in the cited lines; never the conversation date in the fact — the system adds
it; never the subject's name if the line does not say it — it is given by the node), working **message by message to
the last one**, short messages included, and a final check. Example with an invented name. Lots of 10,000; three
reasoning efforts (Luna's levels: none, low, medium — the default — high, xhigh, max).

First panel (tuning):

| Luna, Luna's prompt, lots of 10,000 | Correct | Coverage | Facts kept | Rejections | Time per pass | Cost per pass |
|---|---|---|---|---|---|---|
| **low** | **71.1 %** ✓ | **76.3 %** ✓ | 131 | 27 | 21 s | $0.021-0.029 |
| medium | 66.2 % ✓ | 77.6 % ✓ | 175 | 25 | 56 s | $0.041-0.048 |
| high | 75.4 % ✓ | 88.6 % ✓ | 186 | 23 | 93 s | $0.068-0.075 |
| Terra, adapted prompt (`docs/17` §10.1) | 69.7 % | 79.4 % | 129 | 19 | — | $0.11-0.20 |
| Astra (reference) | 62.7 % | 69.7 % | 105 | 17 | — | ≈ $2 |

Rejections halved (56 → 27). Low against Astra on the first pass: 13 questions won, 4 lost (McNemar p = 0.049). The
low/medium gap is noise (identical first pass; a pass of low differs from the other by 15 questions).

## 5. Confirmation on six unseen days

| Six days Luna never saw, two passes | Correct | Coverage | Facts kept | Rejections | Time per pass | Cost per pass | Cost per million raw tokens |
|---|---|---|---|---|---|---|---|
| **Luna, low** | **75.8 %** ✓ | 83.5 % ✓ | 100 | 18 | **20 s** | **$0.019-0.023** | **≈ $0.46** |
| Luna, medium | 75.8 % ✓ | 84.1 % ✓ | 122 | 26 | 63 s | $0.034-0.040 | ≈ $0.81 |
| Luna, high | 75.0 % ✓ | **90.1 %** ✓ | 159 | 23 | 109 s | $0.062-0.071 | ≈ $1.46 |
| Terra, adapted prompt (`docs/17` §11) | 73.4 % | 85.2 % | 96 | — | — | $0.11-0.19 | ≈ $3.3 |
| Astra (reference) | 65.3 % | 84.1 % | 93 | 12 | — | $1.91 (API equivalent) | ≈ $42 |

- **Luna is qualified on days no tuning saw**: against Astra, 11 questions won, 1 lost (p = 0.006); level with Terra
  (+2.4 points of answers, −1.7 of coverage) for **six to eight times less than Terra and about a hundred times less
  than Astra**.
- **Effort buys completeness, not answers**: the three efforts answer equally well (75.0-75.8 %); "high" adds 6.6
  points of coverage and 59 % more facts, for three times the cost and five times the time. On 62 questions this does
  not show in answers; it would count for rare details the questions do not yet ask.
- Cost per million raw tokens = cost of a pass ÷ raw volume of the panel (45,612 tokens).

## 6. Claude Haiku 5.5

Same price as Luna for calls under 100,000 tokens ($0.10 / $0.50), another lab. In bench 17 (production prompt, effort
low, adaptive thinking), Haiku kept too little (40 facts over the six days, against 105 for Astra), took the
assistant's words for facts (12 rejections) and added numbers absent from the cited lines (16). Effort "low", lots of
10,000:

| First panel | Correct | Coverage | Facts kept | Time per pass | Cost per pass |
|---|---|---|---|---|---|
| **H1 — Luna's prompt** | **70.4 %** ✓ | **79.4 %** ✓ | 179 | 42 s | $0.079-0.087 |
| H2 — a prompt for Haiku, tagged sections (role, priorities), conversation last, closing reminder | 62.7 % ✓ | 69.3 % ✓ | 153 | 36 s | $0.073-0.078 |

The layout Anthropic recommends for long documents (tags, document last, closing reminder) did not help on this task.
H1 confirmed on the second panel:

| Six unseen days | Correct | Coverage | Facts kept | Rejections | Time per pass | Cost per pass |
|---|---|---|---|---|---|---|
| **Haiku 5.5, Luna's prompt, low, lots of 10,000** | **71.8 %** ✓ | **89.6 %** ✓ | 134 | 16 | 44 s | $0.070-0.072 |

Haiku is qualified (against Astra 13 won, 3 lost, p = 0.021). Against Luna low: no significant difference in answers
(5 against 5, then 4 against 9, p = 0.27), +6 points of coverage, about three times the cost (the same text counts ≈ 30 %
more tokens, and it writes more facts). Haiku low resembles Luna high (coverage ≈ 90 %, ≈ $0.07) in two and a half
times less time. **What transfers from one lab to the other**: the same prompt (absolute rule, message by message) and
the same 10,000-token lots take Haiku from 27.5 % to 70-72 %.

## 7. Luna's prompt in English (LongMemEval)

`banc/modeles/consigne_luna_en.txt`: Luna's prompt translated, with the repository's English weekday rule (the nearest
day of that name consistent with the tense) and a neutral example. 100 LongMemEval questions drawn (seed 1109, no
abstention), *S* setting (one memory per question, consolidated session by session), Luna effort low, passes of at most
10,000 tokens. **L0** the repository's English production prompt; **L1** Luna's prompt translated; reference: the
memories of the earlier `confirm-lme` run (gpt-4o-mini, production prompt). Retrieval A, reader and judge of `docs/13`
(gpt-4o-mini). Threshold, fixed before the run: L1 ≥ reference − 5 points.

| 100 questions, *S* setting | Correct answers | Lost lots |
|---|---|---|
| Reference: gpt-4o-mini, English production prompt | 46.0 % | — |
| L0 — Luna, English production prompt | 60.0 % | 0 |
| **L1 — Luna, Luna's prompt in English** | **71.0 %** ✓ | **0** |

- **The prompt transfers to English**: L1 against the reference, 27 questions won, 2 lost (McNemar p < 10⁻⁵); against
  L0, 16 won, 5 lost (p = 0.027) — the same prompt changes help in English as in French.
- Consolidation, reader and judge for the whole run (200 memories, 300 answers): $0.52.
- Since this run, the English mask carries the variant: `consolidation_consigne: petit_modele` sends it.

## 8. Every consolidator tried — first panel

Same six days, same 71 questions, same reader and judge; mean of two passes; effort low unless stated.

| Consolidator | Prompt | Lots | Correct | Coverage | Cost per pass |
|---|---|---|---|---|---|
| GPT-6 Astra (reference) | production | a day | 62.7 % | 69.7 % | ≈ $2 (API equivalent) |
| GPT-6.1 Terra | production | a day | 59.2 % | 58.8 % | $0.11-0.20 |
| GPT-6.1 Terra | adapted to Terra | a day | 69.7 % | 79.4 % | $0.11-0.20 |
| GPT-6 Luna | production | a day | 33.1 % | 31.6 % | $0.01-0.02 |
| GPT-6 Luna | adapted to Terra | a day (≤ 40,000) | 57.0 % | 57.9 % | $0.02 |
| GPT-6 Luna | adapted to Terra | 10,000 | 61.3 % | 63.6 % | $0.03 |
| **GPT-6 Luna, low** | **written for Luna** | **10,000** | **71.1 %** | **76.3 %** | **$0.02-0.03** |
| GPT-6 Luna, medium | written for Luna | 10,000 | 66.2 % | 77.6 % | $0.04-0.05 |
| GPT-6 Luna, high | written for Luna | 10,000 | 75.4 % | 88.6 % | $0.07 |
| Claude Haiku 5.5 | production | a day | 27.5 % (34.5 % without truncation) | 14.5 % (29.4 %) | $0.04 |
| Claude Haiku 5.5 | written for Luna | 10,000 | 70.4 % | 79.4 % | $0.08-0.09 |
| Mistral Small 4 | production | a day | 27.5 % | 23.2 % | $0.02-0.03 |
| Mistral Large 4 | production | a day | 28.2 % (30.3 %) | 24.1 % (26.3 %) | $0.09-0.16 |

The Mistral models were only tried with the production prompt; as with Luna and Haiku, a prompt written for them could
change a lot — not measured.

## 9. Limits

62 and 71 questions per panel, one memory (the agent's, in French); the human blind review of facts is not done; the
judge is Terra. The bench consolidates each panel day from a fixed starting point; production consolidates a memory that
keeps growing.

## 10. In production on the agent

Since 9/11/2026 the agent's memory is consolidated by **Luna, low, with Luna's prompt**, in passes of at most 10,000
tokens; the consolidation tool now chains passes until no lot is left (40 at most). A real run on a copy of a heavy day
(≈ 27,000 raw tokens): Luna 78 facts, 11 rejections, 233 s; Terra in production on the same day: 77 facts, 11
rejections, 267 s. The raw lot now closes at 10,000 tokens or every night (`docs/18` §11).
