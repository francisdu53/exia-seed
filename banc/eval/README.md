# banc/eval — the evaluation behind `docs/22` (two memories, one web)

Scripts only. The benchmark data (LoCoMo, LongMemEval), the consolidated benchmark memories, the runs, the vectors and
everything about the agent's real messages are **not** published. The scripts and comments are in French, like the
engineering log of that period; `docs/22` is the English account of what they measured.

## What is here

| Script | Role |
|---|---|
| `preparer.py` | copies the consolidated benchmark memories (one per conversation + the fused one) and fills the fused raw log |
| `sceller.py`, `scelle.json`, `scelle_verdict.json` | the sealed question sets: tuning / test / verdict (question ids only) |
| `fournir_seed.py` | contenders S1 (`memoire_chercher`, 0.9.15) and S2 (the watch, 0.9.16), with sensors |
| `fournir_n.py`, `n.py` | the bench prototype of the new engine (`N1` memories, `Nb` raw, `NF1` both, options for every gear tried) |
| `fournir_rag.py` | contenders with embeddings (bge-m3 on CPU): R dense on raw turns, Rh hybrid BM25 + dense (RRF), Rp dense on memories |
| `paqueter.py` | the same token budget for everyone (whole items only; 450 / 1,350 / 4,500 tokens; o200k tokenizer) |
| `preuves.py` | the free evidence sensor: is a gold evidence turn inside the block? (no model, no token) |
| `lire_juger.py`, `rapport.py` | reader and judge (GPT-6.1 Terra), paired McNemar tests, bootstrap intervals |
| `regler_n.py`, `regler_nb.py`, `regler_s2.py` | weights fitted on the TUNING sets only (logistic regression; S2r = the watch refitted as a fairness control) |
| `ecrire_cartes.py` | the « written maps » gear (N2), measured and dropped |
| `diagnostic_trou.py` | the lexical-gap diagnosis (N0) |
| `bruit.py`, `echelle.py`, `fusion_eval.py`, `rapport_tests_23nov.py` | the 23/11 tests: damaged questions, interference (memories of 1 → 500 conversations), their report |
| `lire_grille_correcteur.py` | reads the corrector and interference grids |
| `equiv_010.py` | checks that the engine shipped in the plugin (`deux_memoires.py`) matches this prototype |
| `../harnais/` | shared helpers: questions, reading and judging prompts, model calls |
| `poids_*.json`, `reglages_*.json` | the fitted weights and gear settings, as used for the results of `docs/22` |
| `interference/` | the groups of conversations used for the interference curve (seed 42) |

## Running

Datasets go in `../bancs/donnees/` (`locomo10.json`, `longmemeval_oracle.json`, and the LongMemEval oracle converted to
the LoCoMo format by the scripts of `banc/longmemeval/`). The SEED contenders import the plugin, so they run inside the
agent's container image; the embedding contenders run in any Python environment with `sentence-transformers`
(`PYTHON_EMBEDDINGS`). Order: `preparer.py` → `sceller.py` → `fournir_*.py` → `paqueter.py` → `preuves.py` (no token) →
`lire_juger.py` → `rapport.py`. Each script's docstring gives its exact command line.

`scelle.json` is published without its section about the agent's real messages (the phase-2 sealing rule); its hash
therefore differs from the one recorded in the run manifests.

The frozen copy of the watch is read from `paquets/seed-1.0.0`: the watch was numbered 1.0.0 while it was built and renamed 0.9.16 when published (1.0.0 is kept for the version validated in real life); the scripts keep the folder name and call it « 1.0.0 » in their comments.
