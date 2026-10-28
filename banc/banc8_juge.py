#!/usr/bin/env python3
"""Banc 8, temps 3 (conteneur, GPT-6) — FCM, FCM + pistes, plein texte, puis le juge aveugle (docs/08).

Pour chaque message où le modèle a choisi de chercher (temps 1), LA MÊME requête est donnée aux
moteurs ; chacun rend au plus 9 faits (3 sujets × 3). Les embeddings viennent du temps 2 (hôte).
Le juge voit l'union, mélangée, sans étiquette — consigne identique au banc 06 (banc_juge.SYS_J).

    python3 banc8_juge.py /opt/data/workspace/banc-6b /opt/data/workspace/banc-8 [plugins]
"""
import hashlib
import json
import random
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SOURCE, SORTIE = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, "/opt/hermes")
sys.path.insert(0, sys.argv[3] if len(sys.argv) > 3 else "/opt/data/plugins")
from exia_seed import rappel as R                                           # noqa: E402
from exia_seed.consolidation import appel_llm_hermes                        # noqa: E402
from exia_seed.requete import Lecteur                                       # noqa: E402
from exia_seed.util import estimer_tokens                                   # noqa: E402

SUJETS, PAR_SUJET, PAQUET = 3, 3, 40
SYS_J = ("Tu évalues des souvenirs proposés à un assistant personnel. On te donne le message de l'utilisateur, la "
         "réponse que l'assistant a réellement donnée (pour le contexte seulement) et des souvenirs numérotés. "
         "Indique ceux qui auraient été UTILES à l'assistant pour comprendre la demande ou bien y répondre : une "
         "information pertinente qu'il gagne à avoir sous les yeux. Un souvenir seulement sur le même thème, sans "
         "apport pour CE message, n'est PAS utile. Sois exigeant. Réponds UNIQUEMENT par un objet JSON : "
         '{"utiles": [numéros]}')
CACHE_F = SORTIE / "appels8.jsonl"
CACHE = {json.loads(l)["cle"]: json.loads(l) for l in CACHE_F.read_text(encoding="utf-8").splitlines()} if CACHE_F.exists() else {}
llm = appel_llm_hermes("low")


def juger(n, message, reponse, faits):
    faits = sorted(set(faits)); random.Random(n).shuffle(faits)
    utiles = set()
    for k in range(0, len(faits), PAQUET):
        lot = faits[k:k + PAQUET]
        liste = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(lot))
        cle = f"juge8:{n}:{k}:" + hashlib.sha256(liste.encode()).hexdigest()[:10]
        if cle not in CACHE:
            rep = llm([{"role": "system", "content": SYS_J}, {"role": "user", "content":
                       f"MESSAGE DE L'UTILISATEUR\n{message}\n\nRÉPONSE DE L'ASSISTANT (contexte)\n{reponse[:600]}\n\nSOUVENIRS\n{liste}"}])
            m = re.search(r"\{.*\}", rep or "", re.S)
            try:
                u = json.loads(m.group(0)).get("utiles", []) if m else []
            except ValueError:
                u = []
            CACHE[cle] = {"cle": cle, "utiles": u, "tokens": (len(SYS_J) + len(message) + 600 + len(liste) + len(rep or "")) // 4}
            with CACHE_F.open("a", encoding="utf-8") as f:
                f.write(json.dumps(CACHE[cle], ensure_ascii=False) + "\n")
        for i in CACHE[cle]["utiles"] or []:
            if isinstance(i, int) and 1 <= i <= len(lot):
                utiles.add(lot[i - 1])
    return utiles


def plein_texte(rp, m, requete):
    """BM25 sur les faits, sujets classés par leur meilleur fait, 3 × 3."""
    mots = [w for w in R._graphe._norm(requete).split() if len(w) >= 4 and w not in R._mots_vides()]
    if not mots:
        return []
    try:
        lignes = m.fts.execute("select rowid from f where f match ? order by bm25(f) limit 60",
                               (" OR ".join(f'"{w}"' for w in mots),)).fetchall()
    except Exception:
        return []
    groupes = {}
    for (i,) in lignes:
        n = m.faits[i]["noeud"]
        if n not in groupes and len(groupes) >= SUJETS:
            continue
        if len(groupes.setdefault(n, [])) < PAR_SUJET:
            groupes[n].append(m.faits[i]["texte"])
    return [f for v in groupes.values() for f in v]


def main() -> int:
    rejeu = {json.loads(l)["n"]: json.loads(l) for l in (SOURCE / "rejeu.jsonl").read_text(encoding="utf-8").splitlines()}
    requetes = [json.loads(l) for l in (SORTIE / "requetes.jsonl").read_text(encoding="utf-8").splitlines()]
    emb = {json.loads(l)["n"]: json.loads(l)["embeddings"] for l in (SORTIE / "embeddings.jsonl").read_text(encoding="utf-8").splitlines()}
    lecteurs, resultats = {}, []
    for r in requetes:
        if not r["requete"]:
            continue
        s, q, n = r["instantane"], r["requete"], r["n"]
        if s not in lecteurs:
            lecteurs[s] = Lecteur(SOURCE / "instantanes" / s, implicites=("francis", "nexa"))
        L = lecteurs[s]
        instant = datetime.fromisoformat(r["instant"])
        t0 = time.perf_counter()
        c = L.chercher(q, SUJETS, instant)
        lat_fcm = (time.perf_counter() - t0) * 1000
        fcm = [f["fait"] for x in c.get("resultats", []) for f in x["faits"]]
        pistes = []
        if c.get("resultats"):
            lu = L.lire(c["resultats"][0]["sujet"], instant)
            pistes = [t for p in lu.get("pistes", []) for t in p["faits"]]
        fcm_p = [f["fait"] for x in c.get("resultats", [])[:2] for f in x["faits"]]
        fcm_p += [t for t in pistes if t not in fcm_p][:9 - len(fcm_p)]
        m = L.r.memoire()
        bm25 = plein_texte(L.r, m, q)
        e = [f for x in emb.get(n, []) for f in x["faits"]]
        entree = sorted({et for et, v in L.r.activer(m, q)["etages"].items() if v}) or ["rien"]
        moteurs = {"FCM": fcm, "FCM+pistes": fcm_p, "Embeddings": e, "Plein texte": bm25}
        union = set().union(*map(set, moteurs.values()))
        l = rejeu[n]
        utiles = juger(n, l["message"], l["reponse"], list(union)) if union else set()
        resultats.append({"n": n, "requete": q, "entree_fcm": entree, "latence_fcm_ms": round(lat_fcm, 2),
                          "utiles": sorted(utiles), **{k: v for k, v in moteurs.items()}})
        print(f"  {n:3} « {q[:40]:40} » union {len(union):2} utiles {len(utiles):2} · entrée {entree}", flush=True)
    (SORTIE / "resultats8.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in resultats), encoding="utf-8")

    # Mesures
    noms = ["FCM", "FCM+pistes", "Embeddings", "Plein texte"]
    tot_utiles = sum(len(x["utiles"]) for x in resultats)
    bilan = {"messages_avec_requete": len(resultats), "messages_sans_requete": len(requetes) - len(resultats),
             "utiles_dans_l_union": tot_utiles}
    for k in noms:
        trouves = sum(len(set(x[k]) & set(x["utiles"])) for x in resultats)
        proposes = sum(len(x[k]) for x in resultats)
        autres = [o for o in noms if o != k and not (k.startswith("FCM") and o.startswith("FCM"))]
        seul = sum(len((set(x[k]) & set(x["utiles"])) - set().union(*(set(x[o]) for o in autres))) for x in resultats)
        bilan[k] = {"utiles_trouves": trouves, "rappel_relatif": round(trouves / tot_utiles, 3) if tot_utiles else None,
                    "precision": round(trouves / proposes, 3) if proposes else None, "faits_proposes": proposes,
                    "parle": sum(1 for x in resultats if x[k]),
                    "parle_pour_rien": sum(1 for x in resultats if x[k] and not set(x[k]) & set(x["utiles"])),
                    "seul_a_trouver": seul,
                    "tokens_moyens": round(sum(estimer_tokens(" ".join(x[k])) for x in resultats) / max(1, len(resultats)))}
    ent = defaultdict(lambda: [0, 0, 0])
    for x in resultats:
        cle = "+".join(x["entree_fcm"]); ent[cle][0] += 1
        ent[cle][1] += len(set(x["FCM"]) & set(x["utiles"])); ent[cle][2] += len(set(x["Embeddings"]) & set(x["utiles"]))
    bilan["par_entree_fcm"] = {k: {"messages": v[0], "utiles_FCM": v[1], "utiles_Embeddings": v[2]} for k, v in ent.items()}
    lat = sorted(x["latence_fcm_ms"] for x in resultats)
    bilan["latence_fcm_p95_ms"] = lat[int(0.95 * len(lat)) - 1] if lat else None
    bilan["cout_banc_tokens"] = sum(v.get("tokens", 0) for v in CACHE.values())
    (SORTIE / "bilan8.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(bilan, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
