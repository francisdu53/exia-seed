#!/usr/bin/env python3
"""Banc « souvenirs qui remontent » (phase 2 du rappel, docs/11) — mesurer AVANT d'activer.

Question : si EXIA SEED montrait à Nexa, avec chaque message de Francis, les souvenirs qu'il fait remonter,
seraient-ils UTILES, ou du bruit ? Et quand il n'y a rien d'utile, se tairait-il ?

Protocole (contre l'auto-illusion) :
- les VRAIS messages de Francis du 01/10 au 16/10, chacun rejoué sur la mémoire TELLE QU'ELLE ÉTAIT (instantané
  git de la dernière consolidation antérieure) — aucun fait appris après le message ;
- messages « triviaux » (« ok », « merci », commandes) écartés exactement comme Hermès (is_trivial_prompt) ;
- deux moteurs : V1 = le rappel actuel (Rappeleur.rappeler, celui du journal à blanc) ; V2 = la recherche
  optimisée du 29/09 (Lecteur.chercher) appliquée au message entier ;
- juge AVEUGLE (GPT-6, consigne du banc 8 : « utiles… sois exigeant ») sur l'union, mélangée, sans étiquette ;
- seuil et format choisis sur le RÉGLAGE (01-08/10), annoncés sur la VÉRIFICATION (09-16/10).

    rejeu  : python3 mesure.py rejeu <memoire> <sortie> <plugins>     (conteneur, sans modèle)
    juge   : python3 mesure.py juge  <memoire> <sortie> <plugins>     (conteneur, GPT-6)
    bilan  : python3 mesure.py bilan <memoire> <sortie> <plugins>
"""
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ETAPE, MEMOIRE, SORTIE, PLUGINS = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
DEBUT, BASCULE = "2026-10-01T00:00", "2026-10-09T00:00"
PARIS = ZoneInfo("Europe/Paris")
IMPLICITES = ("francis", "nexa")
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, PLUGINS); sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, "/opt/data/workspace/banc-8")
MODE = sys.argv[5] if len(sys.argv) > 5 else ""
sys.argv = [sys.argv[0], str(SORTIE), str(SORTIE), PLUGINS]


def git(*a, binaire=False):
    return subprocess.run(["git", "-C", str(MEMOIRE), "-c", "safe.directory=*", *a], capture_output=True, check=True,
                          text=not binaire).stdout


def instantanes():
    return [(int(ct), h) for h, ct in (l.split() for l in git("log", "--reverse", "--format=%H %ct").splitlines())]


def messages():
    """[(instant Paris naïf, message de Francis, réponse de Nexa qui suit)] — même lecture que banc_rappel.py."""
    sortie = []
    for f in sorted((MEMOIRE / "raw").glob("*.md")):
        texte = f.read_text(encoding="utf-8")
        m = re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})", texte, re.M)
        o = re.search(r"^ouvert_le:\s*\S+T(\d\d:\d\d)", texte, re.M)
        if not m:
            continue
        jour = datetime.fromisoformat(m.group(1))
        tours, courant = [], None
        for ligne in texte.split("## Échanges", 1)[-1].splitlines():
            t = re.match(r"^\[(\d\d):(\d\d) (\w+)\] ?(.*)$", ligne)
            if t:
                courant = [t.group(3), f"{t.group(1)}:{t.group(2)}", t.group(4)]; tours.append(courant)
            elif courant and ligne.strip() and not ligne.lstrip().startswith("<!--"):
                courant[2] += "\n" + ligne
        for k, (qui, hhmm, txt) in enumerate(tours):
            if qui != "francis":
                continue
            from datetime import timedelta
            j = jour + timedelta(days=1) if o and hhmm < o.group(1) else jour
            reponse = next((t[2] for t in tours[k + 1:] if t[0] == "nexa"), "")
            sortie.append((datetime.fromisoformat(f"{j.date()}T{hhmm}"), txt.strip(), reponse.strip()))
    return sortie


def extraire(commit, dossier: Path):
    from exia_seed import graphe as G
    if (dossier / "graphe" / "aretes.json").exists():
        return
    dossier.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(git("archive", commit, binaire=True))) as t:
        t.extractall(dossier, members=[x for x in t.getmembers() if x.name.startswith(("pages/", "INDEX.md", "thesaurus.json"))],
                     filter="data")
    (dossier / "raw").mkdir(exist_ok=True)
    G.calculer(dossier, implicites=IMPLICITES)


def rejeu() -> int:
    from agent.memory_provider import is_trivial_prompt
    from exia_seed.rappel import Rappeleur
    from exia_seed.requete import Lecteur
    snaps, lignes, lecteurs = instantanes(), [], {}
    for n, (instant, texte, reponse) in enumerate(messages()):
        if instant.isoformat() < DEBUT or is_trivial_prompt(texte):
            continue
        avant = [h for ct, h in snaps if ct < instant.replace(tzinfo=PARIS).timestamp()]
        h = avant[-1][:7]
        if h not in lecteurs:
            d = SORTIE / "instantanes" / h
            extraire(h, d)
            r = Rappeleur(d, implicites=IMPLICITES)
            lecteurs[h] = (r, Lecteur(d, implicites=IMPLICITES, rappeleur=r))
        r, L = lecteurs[h]
        m = r.memoire()
        v1 = r.rappeler(texte, instant)
        complets = []                                   # le journal tronque à 90 caractères : on retrouve le fait entier
        for x in v1.get("faits", []):
            plein = next((f["texte"] for f in m.faits if f["fichier"] == x["page"] and f["texte"].startswith(x["fait"])), x["fait"])
            complets.append({"fait": plein, "score": x["score"], "page": x["page"]})
        c = L.chercher(texte, 5, instant, faits_max=8)
        paires = [(y["sujet"], f["fait"]) for y in c.get("resultats", []) for f in y["faits"]]
        v2 = [{"fait": fait, "rang": k, "page": sujet} for k, (sujet, fait) in enumerate(paires)]
        v2 += [{"fait": p["fait"], "rang": 90 + k, "page": p.get("sujet"), "piste": True}
               for k, p in enumerate((c.get("pistes") or {}).get("faits", []))]
        lignes.append({"n": n, "instant": instant.isoformat(timespec="minutes"), "tranche": "verification" if instant.isoformat() >= BASCULE else "reglage",
                       "message": texte[:1500], "reponse": reponse[:800], "instantane": h, "V1": complets, "V1_tokens": v1.get("tokens", 0), "V2": v2})
    (SORTIE / "rejeu.jsonl").write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lignes), encoding="utf-8")
    print(f"{len(lignes)} messages non triviaux rejoués ({sum(l['tranche'] == 'reglage' for l in lignes)} réglage, "
          f"{sum(l['tranche'] == 'verification' for l in lignes)} vérification) · {len(lecteurs)} instantanés · "
          f"V1 parle {sum(1 for l in lignes if l['V1'])} fois · V2 parle {sum(1 for l in lignes if l['V2'])} fois")
    return 0


def juge() -> int:
    import banc8_juge as J
    lignes = [json.loads(l) for l in (SORTIE / "rejeu.jsonl").read_text(encoding="utf-8").splitlines()]
    for k, l in enumerate(lignes):
        union = sorted({x["fait"] for x in l["V1"] + l["V2"]})
        for essai in range(4):                          # une expiration côté Codex ne doit pas tout arrêter (16/10)
            try:
                l["utiles"] = sorted(J.juger(700_000 + l["n"], l["message"], l["reponse"], union)) if union else []
                break
            except Exception as e:
                print(f"  ⚠ message {l['n']} : {type(e).__name__} — essai {essai + 1}/4", flush=True)
                if essai == 3:
                    raise
                import time; time.sleep(20)
        if k % 25 == 0:
            print(f"  {k}/{len(lignes)} · coût cumulé {sum(v.get('tokens', 0) for v in J.CACHE.values())} tokens", flush=True)
    (SORTIE / "juge.jsonl").write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lignes), encoding="utf-8")
    print(f"jugé · coût total du juge {sum(v.get('tokens', 0) for v in J.CACHE.values())} tokens")
    return 0


def mesurer(lignes, choisir):
    """choisir(ligne) → liste de faits montrés. Rend les indicateurs du « souvenir qui remonte »."""
    parle = utiles_montres = montres = pour_rien = bon_silence = silence_rate = 0
    utiles_dispo = 0
    for l in lignes:
        u = set(l["utiles"]); f = choisir(l)
        utiles_dispo += bool(u)
        if f:
            parle += 1; montres += len(f); k = len(set(f) & u); utiles_montres += k
            pour_rien += (k == 0)
        else:
            bon_silence += (not u); silence_rate += bool(u)
    n = len(lignes)
    return {"messages": n, "parle": parle, "messages_avec_utile_dispo": utiles_dispo,
            "aide": parle - pour_rien, "pour_rien": pour_rien, "silence_juste": bon_silence, "silence_manque": silence_rate,
            "faits_montres": montres, "faits_utiles": utiles_montres,
            "precision": round(utiles_montres / montres, 3) if montres else None}


def bilan() -> int:
    lignes = [json.loads(l) for l in (SORTIE / "juge.jsonl").read_text(encoding="utf-8").splitlines()]
    res = {}
    for tranche in ("reglage", "verification"):
        L = [l for l in lignes if l["tranche"] == tranche]
        t = res.setdefault(tranche, {})
        for seuil in (0.0, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.8):
            for kmax in (3, 5, 8):
                t[f"V1 seuil {seuil} max {kmax}"] = mesurer(L, lambda l: [x["fait"] for x in l["V1"] if x["score"] >= seuil][:kmax])
        for kmax in (3, 5, 8):
            t[f"V2 max {kmax}"] = mesurer(L, lambda l: [x["fait"] for x in l["V2"]][:kmax])
            t[f"V2 sans pistes max {kmax}"] = mesurer(L, lambda l: [x["fait"] for x in l["V2"] if not x.get("piste")][:kmax])
    (SORTIE / "bilan.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for tranche, t in res.items():
        print(f"\n── {tranche.upper()} ({next(iter(t.values()))['messages']} messages, dont {next(iter(t.values()))['messages_avec_utile_dispo']} avec un souvenir utile disponible)")
        print(f"{'variante':28}{'parle':>7}{'aide':>6}{'pour rien':>11}{'silence juste':>15}{'silence manqué':>16}{'précision':>11}")
        for k, v in t.items():
            print(f"{k:28}{v['parle']:>7}{v['aide']:>6}{v['pour_rien']:>11}{v['silence_juste']:>15}{v['silence_manque']:>16}{str(v['precision']):>11}")
    return 0


def sujets() -> int:
    """Le format « le sujet d'abord » : ce qui remonte, c'est d'abord un SUJET (« application de liste de courses »),
    puis un ou deux faits. Mesures par sujet et par section, seuil réglé sur le réglage, vérifié sur la vérification."""
    from collections import Counter, defaultdict
    from exia_seed import pages as P
    lignes = [json.loads(l) for l in (SORTIE / "juge.jsonl").read_text(encoding="utf-8").splitlines()]
    section_de, titre_de = {}, {}
    for d in sorted((SORTIE / "instantanes").iterdir()):
        for pg in P.lister(d / "pages"):
            titre_de[pg.chemin.name] = pg.titre()
            for cle in [c for c, _ in P.SECTIONS]:
                for l in pg.sections[cle]:
                    section_de[P._RE_META.sub("", l[2:]).strip()] = cle
    par_section = defaultdict(lambda: [0, 0])
    for l in lignes:
        u = set(l["utiles"])
        for x in l["V1"]:
            s = section_de.get(x["fait"], "?"); par_section[s][0] += 1; par_section[s][1] += x["fait"] in u
    print("utilité des faits du rappel actuel (V1) par section :")
    for s, (n, k) in sorted(par_section.items(), key=lambda z: -z[1][0]):
        print(f"  {s:12} {k:4}/{n:<4} utiles ({100 * k / max(1, n):.0f} %)")

    def format_sujets(l, seuil, max_sujets, faits_par_sujet):
        groupes = defaultdict(list)
        for x in l["V1"]:
            if x["score"] >= seuil:
                groupes[x["page"]].append(x)
        ordre = sorted(groupes, key=lambda p: -max(x["score"] for x in groupes[p]))[:max_sujets]
        montre = []
        for p in ordre:
            fs = sorted(groupes[p], key=lambda x: (section_de.get(x["fait"]) != "procedural", -x["score"]))[:faits_par_sujet]
            montre.append((p, [x["fait"] for x in fs]))
        return montre

    print()
    res = {}
    for tranche in ("reglage", "verification"):
        L = [l for l in lignes if l["tranche"] == tranche]
        print(f"── {tranche.upper()} ({len(L)} messages) — format « le sujet d'abord »")
        print(f"{'variante':34}{'parle':>7}{'sujet utile':>13}{'pour rien':>11}{'faits utiles':>14}{'précision faits':>17}")
        for seuil in (0.0, 0.5, 0.55, 0.6, 0.65, 0.7):
            for ms, fp in ((2, 2), (3, 2), (3, 1)):
                parle = sujet_utile = pour_rien = montres = utiles = 0
                for l in L:
                    u = set(l["utiles"]); m = format_sujets(l, seuil, ms, fp)
                    if not m:
                        continue
                    parle += 1
                    pages_utiles = {x["page"] for x in l["V1"] if x["fait"] in u}
                    ok = any(p in pages_utiles for p, _ in m)
                    sujet_utile += ok; pour_rien += (not ok)
                    fs = [f for _, ff in m for f in ff]; montres += len(fs); utiles += len(set(fs) & u)
                k = f"seuil {seuil} · {ms} sujets × {fp} faits"
                res.setdefault(tranche, {})[k] = {"parle": parle, "sujet_utile": sujet_utile, "pour_rien": pour_rien,
                                                   "faits_montres": montres, "faits_utiles": utiles}
                print(f"{k:34}{parle:>7}{sujet_utile:>13}{pour_rien:>11}{utiles:>14}{(str(round(utiles / montres, 3)) if montres else '—'):>17}")
    (SORTIE / "bilan_sujets.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def _section_de():
    from exia_seed import pages as P
    section_de = {}
    for d in sorted((SORTIE / "instantanes").iterdir()):
        for pg in P.lister(d / "pages"):
            for cle in [c for c, _ in P.SECTIONS]:
                for l in pg.sections[cle]:
                    section_de[P._RE_META.sub("", l[2:]).strip()] = cle
    return section_de


def _sujets_montres(l, section_de, seuil=0.5, max_sujets=3, faits_par_sujet=2):
    from collections import defaultdict
    groupes = defaultdict(list)
    for x in l["V1"]:
        if x["score"] >= seuil:
            groupes[x["page"]].append(x)
    ordre = sorted(groupes, key=lambda p: -max(x["score"] for x in groupes[p]))[:max_sujets]
    return [(p, [x["fait"] for x in sorted(groupes[p], key=lambda x: (section_de.get(x["fait"]) != "procedural", -x["score"]))[:faits_par_sujet]])
            for p in ordre]


def fiches() -> int:
    """docs/12 — la fiche d'identité aide-t-elle ? Chaque fiche est rédigée DEPUIS LA PAGE TELLE QU'ELLE ÉTAIT à
    l'instant du message (pas de fiche d'aujourd'hui pour un message du 1er octobre), une fois par version distincte
    de page ; puis le juge aveugle (même consigne) dit si la fiche des sujets remontés était utile.
    `fiches compter` : combien de versions de pages, sans appel."""
    import hashlib
    from exia_seed import fiches as F, pages as P
    lignes = [json.loads(l) for l in (SORTIE / "juge.jsonl").read_text(encoding="utf-8").splitlines()]
    section_de = _section_de()
    versions, besoin = {}, []                      # sha → (instantané, page) ; par message : [(page, sha)]
    for l in lignes:
        m = []
        for page, _ in _sujets_montres(l, section_de):
            f = SORTIE / "instantanes" / l["instantane"] / "pages" / page
            sha = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
            versions.setdefault(sha, f); m.append((page, sha))
        besoin.append(m)
    print(f"{sum(1 for m in besoin if m)} messages parlent · {len(versions)} versions de pages distinctes")
    if MODE == "compter":
        return 0
    cache_f = SORTIE / "fiches_banc.jsonl"
    cache = {json.loads(x)["sha"]: json.loads(x) for x in cache_f.read_text(encoding="utf-8").splitlines()} if cache_f.exists() else {}
    from exia_seed.consolidation import appel_llm_hermes
    llm = appel_llm_hermes("low")
    a_faire = [(sha, f) for sha, f in versions.items() if sha not in cache]
    while a_faire:                                  # un lot = des nœuds distincts (rediger range par nœud)
        lot, vus = [], set()
        for sha, f in list(a_faire):
            pg = P.Page.charger(f)
            if pg.entete.get("node") in vus or len(lot) >= F.PAGES_PAR_APPEL:
                continue
            vus.add(pg.entete.get("node")); lot.append((sha, pg)); a_faire.remove((sha, f))
        r = F.rediger([pg for _, pg in lot], llm, "2026-10-16", ecrire=False, connus=IMPLICITES)
        refus = {x[0]: x[1] for x in r["refusees"]}
        with cache_f.open("a", encoding="utf-8") as out:
            for sha, pg in lot:
                n = str(pg.entete.get("node"))
                cache[sha] = {"sha": sha, "noeud": n, "fiche": r["proposees"].get(n, ""), "refus": refus.get(n, ""),
                              "tokens": (r["tokens_entree"] + r["tokens_sortie"]) // max(1, len(lot))}
                out.write(json.dumps(cache[sha], ensure_ascii=False) + "\n")
        print(f"  {len(cache)}/{len(versions)} fiches · {sum(v['tokens'] for v in cache.values())} tokens", flush=True)
    import banc8_juge as J
    for l, m in zip(lignes, besoin):
        items = {f"{P.Page.charger(SORTIE / 'instantanes' / l['instantane'] / 'pages' / page).titre()} : {cache[sha]['fiche']}": page
                 for page, sha in m if cache[sha]["fiche"]}
        l["fiches"] = {page: cache[sha]["fiche"] for page, sha in m}
        u = set()
        for essai in range(4):
            try:
                u = J.juger(800_000 + l["n"], l["message"], l["reponse"], list(items)) if items else set()
                break
            except Exception as e:
                print(f"  ⚠ message {l['n']} : {type(e).__name__} — essai {essai + 1}/4", flush=True)
                if essai == 3:
                    raise
                import time; time.sleep(20)
        l["fiches_utiles"] = sorted(items[x] for x in u)
    (SORTIE / "juge_fiches.jsonl").write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lignes), encoding="utf-8")
    for tranche in ("reglage", "verification"):
        parle = sujet_fait = sujet_fiche = sujet_un = fiche_seule = 0
        for l, m in zip(lignes, besoin):
            if l["tranche"] != tranche or not m:
                continue
            parle += 1
            u = set(l["utiles"]); pages_utiles = {x["page"] for x in l["V1"] if x["fait"] in u}
            montres_utiles = {p for p, fs in _sujets_montres(l, section_de) if set(fs) & u}
            a = bool(montres_utiles); b = bool(l["fiches_utiles"])
            sujet_fait += a; sujet_fiche += b; sujet_un += (a or b); fiche_seule += (b and not a)
        print(f"── {tranche.upper()} : {parle} messages parlent · utiles par un FAIT montré {sujet_fait} · par la FICHE {sujet_fiche}"
              f" · par l'un ou l'autre {sujet_un} ({100 * sujet_un / max(1, parle):.0f} %) · dont fiche seule {fiche_seule} · pour rien {parle - sujet_un}")
    print(f"coût : fiches {sum(v['tokens'] for v in cache.values())} tokens · juge {sum(v.get('tokens', 0) for k, v in J.CACHE.items() if k.startswith('juge8:8'))} tokens")
    return 0


_RAP = {}


def _rappeleur(racine: Path):
    from exia_seed.rappel import Rappeleur
    if str(racine) not in _RAP:
        _RAP[str(racine)] = Rappeleur(racine, implicites=IMPLICITES)
    return _RAP[str(racine)]


def _instantane_mots(h: str) -> Path:
    """Copie de l'instantané où chaque page reçoit ses MOTS DISTINCTIFS (docs/12 §9), écrits une fois sur la mémoire
    du 16/10 matin (propositions-mots.json) puis filtrés par les alias de la page À L'ÉPOQUE : aucun mot du futur."""
    from exia_seed import fiches as F, pages as P
    d = SORTIE / "instantanes_mots" / h
    if not (d / "graphe").exists():
        props = json.loads(Path("/opt/data/workspace/banc-fiches/propositions-mots.json").read_text(encoding="utf-8"))["mots"]
        shutil.copytree(SORTIE / "instantanes" / h, d)
        for f in (d / "pages").glob("*.md"):
            pg = P.Page.charger(f)
            n = str(pg.entete.get("node"))
            if n in props:
                pg.entete["keywords"] = F.mots_valides(props[n], pg, IMPLICITES)
                pg.ecrire()
    return d


def _rappel_base(h, texte, l, prec):
    r = _rappeleur(SORTIE / "instantanes" / h)
    return r.rappeler(texte, datetime.fromisoformat(l["instant"])), r.memoire()


def _rappel_enveloppes(h, texte, l, prec, racine=None):
    from exia_seed.enveloppes import pour_rappel
    r = _rappeleur(racine or SORTIE / "instantanes" / h)
    t = pour_rappel(texte)
    return (r.rappeler(t, datetime.fromisoformat(l["instant"])) if t.strip() else {"faits": []}), r.memoire()


def _rappel_mots(h, texte, l, prec):
    return _rappel_enveloppes(h, texte, l, prec, racine=_instantane_mots(h))


def _poids(w):
    def f(h, texte, l, prec):
        from exia_seed import rappel as R
        R.POIDS_MOT_COMMUN = w
        return _rappel_mots(h, texte, l, prec)
    return f


# « enveloppes+mots » (16/10, 1er essai) = SEULS les mots distinctifs allumaient un sujet par un mot : rejeté (perdait la
# moitié des souvenirs utiles, dont l'incident des courses). Le moteur a depuis le poids continu POIDS_MOT_COMMUN.
def _rappel_amorce(h, texte, l, prec):
    """docs/12 §10 : tout ce qui est validé (enveloppes, mots distinctifs, règles) + l'amorce du message précédent
    (moins de 30 minutes avant), comme le fournisseur le fera chez Nexa."""
    from exia_seed import rappel as R
    from exia_seed.enveloppes import pour_rappel
    R.POIDS_MOT_COMMUN = 0.5
    r = _rappeleur(_instantane_mots(h))
    t = pour_rappel(texte)
    amorce = None
    if prec and prec[2] and (datetime.fromisoformat(l["instant"]) - datetime.fromisoformat(prec[1]["instant"])).total_seconds() <= 1800:
        amorce = prec[2]
    return (r.rappeler(t, datetime.fromisoformat(l["instant"]), amorce=amorce) if t.strip() else {"faits": []}), r.memoire()


VARIANTES = {"base": _rappel_base, "enveloppes": _rappel_enveloppes, "mots0.5": _poids(0.5), "mots0.75": _poids(0.75),
             "amorce": _rappel_amorce}


def variante() -> int:
    """docs/12 §8 — une correction du RAPPEL, mesurée comme les autres : les 362 messages rejoués sur la mémoire de
    leur époque, au format phase 2 (seuil 0,5, 3 sujets × 2 faits + fiche) ; le juge aveugle ne voit que ce qui est
    NOUVEAU (faits jamais jugés pour ce message, fiches jamais jugées) — le reste est déjà jugé.
    `variante base` doit retrouver le banc des fiches (contrôle de la mesure)."""
    import hashlib
    from collections import defaultdict
    from exia_seed import pages as P
    from exia_seed.rappel import Rappeleur
    nom = MODE or "base"
    fonction = VARIANTES[nom]
    lignes = [json.loads(x) for x in (SORTIE / "juge_fiches.jsonl").read_text(encoding="utf-8").splitlines()]
    textes = {n: (t, rep) for n, (_, t, rep) in enumerate(messages())}
    section_de = _section_de()
    cache_f = SORTIE / "fiches_banc.jsonl"
    fiches = {json.loads(x)["sha"]: json.loads(x) for x in cache_f.read_text(encoding="utf-8").splitlines()}
    rap, res, prec, ecarts = {}, [], None, 0
    for l in lignes:
        texte = textes.get(l["n"], ("", ""))[0]
        if texte[:1500] != l["message"]:
            ecarts += 1; texte = l["message"]          # le brut a bougé : on garde le texte rejoué le 16/10
        h = l["instantane"]
        v, m = fonction(h, texte, l, prec)
        complets = []
        for x in v.get("faits", []):
            plein = next((f["texte"] for f in m.faits if f["fichier"] == x["page"] and f["texte"].startswith(x["fait"])), x["fait"])
            complets.append({"fait": plein, "score": x["score"], "page": x["page"]})
        montre = _sujets_montres({"V1": complets}, section_de)
        shas = {}
        for page, _ in montre:
            f = SORTIE / "instantanes" / h / "pages" / page
            shas[page] = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
        res.append({"n": l["n"], "tranche": l["tranche"], "montre": montre, "shas": shas, "V1": complets})
        prec = (texte, l, v.get("entrees"))
    # fiches manquantes (sujets nouveaux) : rédigées depuis la page de l'époque, comme au banc des fiches
    from exia_seed import fiches as F
    manque = {sha: SORTIE / "instantanes" / next(l["instantane"] for l in lignes if l["n"] == x["n"]) / "pages" / page
              for x in res for page, sha in x["shas"].items() if sha not in fiches}
    if manque:
        from exia_seed.consolidation import appel_llm_hermes
        llm = appel_llm_hermes("low"); a_faire = list(manque.items())
        while a_faire:
            lot, vus = [], set()
            for sha, f in list(a_faire):
                pg = P.Page.charger(f)
                if pg.entete.get("node") in vus or len(lot) >= F.PAGES_PAR_APPEL:
                    continue
                vus.add(pg.entete.get("node")); lot.append((sha, pg)); a_faire.remove((sha, f))
            rf = F.rediger([pg for _, pg in lot], llm, "2026-10-16", ecrire=False, connus=IMPLICITES)
            with cache_f.open("a", encoding="utf-8") as out:
                for sha, pg in lot:
                    n_ = str(pg.entete.get("node"))
                    fiches[sha] = {"sha": sha, "noeud": n_, "fiche": rf["proposees"].get(n_, ""), "refus": "",
                                   "tokens": (rf["tokens_entree"] + rf["tokens_sortie"]) // max(1, len(lot))}
                    out.write(json.dumps(fiches[sha], ensure_ascii=False) + "\n")
        print(f"  {len(manque)} fiches nouvelles rédigées", flush=True)
    import banc8_juge as J
    par_n = {l["n"]: l for l in lignes}
    nouveaux_juges = 0
    for x in res:
        l = par_n[x["n"]]
        deja_faits = {y["fait"] for y in l["V1"] + l["V2"]}
        deja_fiches = {p for p, f in (l.get("fiches") or {}).items() if f}
        items = {}
        for page, fs in x["montre"]:
            for f in fs:
                if f not in deja_faits:
                    items[f] = ("fait", f)
            fi = fiches[x["shas"][page]]["fiche"]
            if fi and page not in deja_fiches:
                titre = P.Page.charger(SORTIE / "instantanes" / l["instantane"] / "pages" / page).titre()
                items[f"{titre} : {fi}"] = ("fiche", page)
        u = set()
        if items:
            nouveaux_juges += 1
            for essai in range(4):
                try:
                    u = J.juger(900_000 + l["n"], l["message"], l["reponse"], list(items)); break
                except Exception as e:
                    print(f"  ⚠ message {l['n']} : {type(e).__name__} — essai {essai + 1}/4", flush=True)
                    if essai == 3:
                        raise
                    import time; time.sleep(20)
        utiles_faits = set(l["utiles"]) | {items[k][1] for k in u if items[k][0] == "fait"}
        utiles_fiches = set(l.get("fiches_utiles") or []) | {items[k][1] for k in u if items[k][0] == "fiche"}
        x["aide"] = any(p in utiles_fiches or set(fs) & utiles_faits for p, fs in x["montre"])
    (SORTIE / f"variante_{nom}.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in res), encoding="utf-8")
    print(f"variante « {nom} » · {ecarts} textes repris du rejeu · {nouveaux_juges} messages avec du nouveau à juger")
    for tranche in ("reglage", "verification"):
        T = [x for x in res if x["tranche"] == tranche]
        parle = sum(1 for x in T if x["montre"]); aide = sum(1 for x in T if x["montre"] and x["aide"])
        sujets = sum(len(x["montre"]) for x in T)
        print(f"── {tranche.upper():13} parle {parle:3} · aidé {aide:3} ({100 * aide / max(1, parle):.0f} %) · pour rien {parle - aide:3} · sujets montrés {sujets}")
    return 0


if __name__ == "__main__":
    sys.exit({"rejeu": rejeu, "juge": juge, "bilan": bilan, "sujets": sujets, "fiches": fiches, "variante": variante}[ETAPE]())
