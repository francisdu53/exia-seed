#!/usr/bin/env python3
"""Banc 6b, partie 3 — la liste d'acceptation validée par Francis (spec §10.3), sur la mémoire ACTUELLE.

Cinq rappels : A (EXIA SEED), Bk (plein texte, budget de A), B5 (plein texte, 5 faits), C (à la
Karpathy, via le modèle) et D (tout donner). Vérification automatique : chaque groupe de mots attendu
doit se trouver dans un même fait rappelé ; « silence » : aucun fait.

    python3 banc_acceptation.py /opt/data/memoire liste_acceptation.json /opt/data/workspace/banc-6b [plugins]
"""
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

MEMOIRE, LISTE, SORTIE = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, "/opt/hermes")
sys.path.insert(0, sys.argv[4] if len(sys.argv) > 4 else "/opt/data/plugins")
from exia_seed import graphe as G                                         # noqa: E402
from exia_seed import rappel as R                                         # noqa: E402
from exia_seed.consolidation import appel_llm_hermes                      # noqa: E402
from exia_seed.util import estimer_tokens                                 # noqa: E402

SYS_C = ("Tu aides un assistant personnel à retrouver ses souvenirs. Tu reçois l'INDEX de sa mémoire (une ligne "
         "par page) et le dernier message de l'utilisateur. Choisis les pages, AU PLUS 3, dont le contenu aiderait "
         "l'assistant à bien comprendre ou traiter ce message ; aucune si rien n'est pertinent. Réponds UNIQUEMENT "
         'par un objet JSON : {"pages": ["nom_du_noeud", ...]}')


def norm(t: str) -> str:
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


def satisfait(groupe, faits) -> bool:
    return any(all(any(alt in norm(f) for alt in mot.split("|")) for mot in groupe) for f in faits)


def main() -> int:
    q = json.loads(LISTE.read_text(encoding="utf-8"))["questions"]
    rp = R.Rappeleur(MEMOIRE, implicites=("francis", "nexa"))
    m = rp.memoire()
    tous = [f["texte"] for f in m.faits]
    index = (MEMOIRE / "INDEX.md").read_text(encoding="utf-8")
    llm = appel_llm_hermes("low")
    maintenant = datetime.now()
    lignes, bilan = [], {k: {"reussies": 0, "groupes": 0, "groupes_ok": 0, "tokens": 0} for k in ("A", "Bk", "B5", "C", "D")}
    for x in q:
        a = [f["fait"] for f in rp.rappeler(x["message"], maintenant)["faits"]]
        seuil, R.SEUIL_FAIT = R.SEUIL_FAIT, 0.0
        try:
            b = [f["fait"] for f in rp.rappeler(x["message"], maintenant, mode="plein_texte")["faits"]]
        finally:
            R.SEUIL_FAIT = seuil
        rep = llm([{"role": "system", "content": SYS_C}, {"role": "user", "content": f"INDEX\n{index}\n\nMESSAGE\n{x['message']}"}])
        mm = re.search(r"\{.*\}", rep or "", re.S)
        pages = (json.loads(mm.group(0)).get("pages") or [])[:3] if mm else []
        c = [f["texte"] for f in m.faits if f["noeud"] in pages]
        # A et Bk travaillent sur le texte complet des faits (la sortie du rappel tronque à 90 caractères)
        complet = lambda courts: [t for t in tous if any(t.startswith(s[:80]) for s in courts)]
        sys_faits = {"A": complet(a), "Bk": complet(b[:len(a)]), "B5": complet(b[:5]), "C": c, "D": tous}
        tokens = {"A": sum(estimer_tokens(t) for t in sys_faits["A"]), "Bk": sum(estimer_tokens(t) for t in sys_faits["Bk"]),
                  "B5": sum(estimer_tokens(t) for t in sys_faits["B5"]),
                  "C": estimer_tokens(SYS_C + index + x["message"]) + sum(estimer_tokens(t) for t in c),
                  "D": sum(estimer_tokens(t) for t in tous)}
        ligne = {"n": x["n"], "message": x["message"], "C_pages": pages}
        for k, faits in sys_faits.items():
            if x.get("silence"):
                ok, g, gok = (not faits), 1, int(not faits)
            else:
                res = [satisfait(gr, faits) for gr in x["attendus"]]
                ok, g, gok = all(res), len(res), sum(res)
            bilan[k]["reussies"] += ok; bilan[k]["groupes"] += g; bilan[k]["groupes_ok"] += gok; bilan[k]["tokens"] += tokens[k]
            ligne[k] = {"reussie": ok, "groupes": f"{gok}/{g}", "faits": len(faits), "tokens": tokens[k]}
        lignes.append(ligne)
        print(f"  {x['n']:2} {x['message'][:44]:44} " + "  ".join(f"{k}:{'✓' if ligne[k]['reussie'] else '✗'}{ligne[k]['groupes']}" for k in sys_faits), flush=True)
    for k in bilan:
        bilan[k]["tokens_moyens"] = round(bilan[k].pop("tokens") / len(q))
        bilan[k]["reussies"] = f"{bilan[k]['reussies']}/{len(q)}"
        bilan[k]["groupes"] = f"{bilan[k].pop('groupes_ok')}/{bilan[k]['groupes']}"
    (SORTIE / "acceptation.json").write_text(json.dumps({"bilan": bilan, "questions": lignes}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(bilan, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
