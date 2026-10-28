#!/usr/bin/env python3
"""Banc 8, temps 1 (conteneur, GPT-6) — le modèle formule la requête qu'il ferait (docs/08 D1).

Entrée : rejeu.jsonl du banc 6b (messages, instantanés sans triche, réponses réelles).
Sortie : requetes.jsonl — pour chaque message rejouable : {"n", "requete" ou null}. Reprise : les appels
déjà faits sont relus dans appels8.jsonl.

    python3 banc8_requetes.py /opt/data/workspace/banc-6b /opt/data/workspace/banc-8 [plugins]
"""
import json
import re
import sys
from pathlib import Path

SOURCE, SORTIE = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, "/opt/hermes")
sys.path.insert(0, sys.argv[3] if len(sys.argv) > 3 else "/opt/data/plugins")
from exia_seed.consolidation import appel_llm_hermes                      # noqa: E402

SYS = ("Tu es Nexa, l'assistante personnelle de Francis. Tu as une mémoire longue que tu peux interroger avec un "
       "outil de recherche par mots-clés : elle contient ce que Francis t'a dit les jours précédents (clients, "
       "règles de travail, rendez-vous, projets, préférences, décisions). Pour le message ci-dessous, décide si "
       "chercher dans cette mémoire t'aiderait à bien répondre. Si oui, écris UNE requête courte : 2 à 6 mots-clés, "
       "pas une phrase. Sinon, n'en écris pas. Réponds UNIQUEMENT par un objet JSON : "
       '{"requete": "mots clés"} ou {"requete": null}')


def main() -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    cache_f = SORTIE / "appels8.jsonl"
    cache = {json.loads(l)["cle"]: json.loads(l) for l in cache_f.read_text(encoding="utf-8").splitlines()} if cache_f.exists() else {}
    llm = appel_llm_hermes("low")
    lignes = [json.loads(l) for l in (SOURCE / "rejeu.jsonl").read_text(encoding="utf-8").splitlines()]
    sortie = []
    for l in lignes:
        if l.get("memoire") == "vide":
            continue
        cle = f"requete:{l['n']}"
        if cle not in cache:
            rep = llm([{"role": "system", "content": SYS}, {"role": "user", "content": l["message"]}])
            m = re.search(r"\{.*\}", rep or "", re.S)
            try:
                q = json.loads(m.group(0)).get("requete") if m else None
            except ValueError:
                q = None
            cache[cle] = {"cle": cle, "requete": q, "tokens": (len(SYS) + len(l["message"]) + len(rep or "")) // 4}
            with cache_f.open("a", encoding="utf-8") as f:
                f.write(json.dumps(cache[cle], ensure_ascii=False) + "\n")
        q = cache[cle]["requete"]
        sortie.append({"n": l["n"], "instantane": l["instantane"], "instant": l["instant"], "requete": q})
        print(f"  {l['n']:3}  {q!r}", flush=True)
    (SORTIE / "requetes.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in sortie), encoding="utf-8")
    avec = sum(1 for x in sortie if x["requete"])
    print(f"{avec}/{len(sortie)} messages avec une requête · ≈ {sum(c['tokens'] for c in cache.values())} tokens")
    return 0


if __name__ == "__main__":
    sys.exit(main())
