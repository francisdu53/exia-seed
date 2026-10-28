# Sources et filiation

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

## Directes
- **Andrej Karpathy — *LLM Wiki***, gist, avril 2026 :
  https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
  Trois couches (sources brutes immuables, wiki maintenu par le modèle, schéma), fichiers `index.md`
  et `log.md`, opérations ingérer / interroger / contrôler.
- **rohitg00 — *LLM Wiki v2***, gist : https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2
  Confiance, récence, suivi des contradictions, courbes d'oubli, relations typées.
- **Hermès Agent**, NousResearch, v2026.9.14 (0.21.3) : https://github.com/NousResearch/hermes-agent
  Contrat `MemoryProvider`, compétence `llm-wiki` v2.1.0.
- **EXIA GHOST**, Francis Babin, 2025-2026 — spécifications internes (non publiées).

## Fondations
- Vannevar Bush, « As We May Think », *The Atlantic*, juillet 1945 — le Memex et ses pistes
  associatives, que Karpathy cite comme ancêtre du LLM Wiki.
- Hermann Ebbinghaus, *Über das Gedächtnis*, 1885 — la courbe de l'oubli.

## Code repris d'EXIA GHOST V2.7.2 (étape 5, 26/09/2026)
- `plugin/exia_seed/moteur/fcm.py` — copie **inchangée** de `exia/causal/fcm.py` (V2.7.2), moteur de
  carte cognitive floue (`FCMEngine`). SHA-256 `bb74b91db6c633809b3677ea74be7d22deec7b5d4e68621d4032f8d88dc8931e`,
  vérifiée par `tests/test_etape_5_graphe.py`.
- Normalisation symétrique d'un graphe (`w = s / √(d(a)·d(b))`) : forme standard de la théorie
  spectrale des graphes (matrice d'adjacence normalisée, Chung, *Spectral Graph Theory*, 1997).
