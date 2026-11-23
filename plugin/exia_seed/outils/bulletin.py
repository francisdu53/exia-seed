#!/usr/bin/env python3
"""Bulletin de santé de la mémoire — DÉTERMINISTE, LECTURE SEULE, aucun appel de modèle (14/11/2026).

Pourquoi : Luna consolidait chez Nexa depuis le 09/11 avec une couverture tombée à 66 % (82 % avec Astra) et les
compteurs du jour ne s'écrivaient plus — personne ne l'a vu pendant cinq jours. Ce bulletin lit les journaux que la
mémoire tient déjà et compare chaque mesure à un seuil. Les seuils sont ceux de l'utilisateur (`bulletin_seuils`).

SILENCIEUX quand tout est vert (un cron sans sortie ne notifie personne) ; une alerte orange ou rouge est imprimée,
donc livrée. `--complet` imprime toujours le bulletin entier (le lundi, ou à la main).

    python3 /opt/data/plugins/exia_seed/outils/bulletin.py              # le cron du matin
    python3 /opt/data/plugins/exia_seed/outils/bulletin.py --complet    # tout, même vert
    python3 bulletin.py --complet --memoire /chemin/vers/memoire --utilisateur francis --jour 2026-11-14   # sur une copie
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Seuils proposés (14/11/2026) — c'est l'utilisateur qui les fixe, dans config.yaml : memory.exia_seed.bulletin_seuils
SEUILS = {
    "couverture_orange": 75.0,     # % de ses messages (≥ 6 mots) cités par au moins un fait, sur 7 jours
    "couverture_rouge": 65.0,
    "rejets_orange": 15.0,         # % des faits proposés refusés au contrôle de citation, sur 7 jours
    "rejets_rouge": 25.0,
    "messages_min": 10,            # en dessous, couverture et rejets sont affichés mais ne déclenchent rien
    "attente_heures": 2,           # un lot fermé et pas consolidé depuis plus longtemps : rouge
}
ENTETE = re.compile(r"^\[(\d\d:\d\d) ([a-z_]+)\] ?(.*)$")
SRC = re.compile(r"<!--.*?src:(\S+)")
REF = re.compile(r"raw/([^:]+):(\d+)(?:-(\d+))?")


def jsonl(chemin: Path):
    if not chemin.exists():
        return []
    sortie = []
    for l in chemin.read_text(encoding="utf-8").splitlines():
        try:
            sortie.append(json.loads(l))
        except ValueError:
            pass
    return sortie


def reglages():
    """Les réglages d'EXIA SEED quand on tourne chez l'agent ; des défauts sinon (copie, banc)."""
    try:
        sys.path.insert(0, "/opt/hermes")
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from exia_seed import config as _config
        from hermes_cli.config import load_config
        r = _config.charger()
        bloc = ((load_config() or {}).get("memory") or {}).get("exia_seed") or {}
        r["bulletin_seuils"] = bloc.get("bulletin_seuils") or {}
        from hermes_constants import get_hermes_home
        r["_memoire"] = str(Path(get_hermes_home()) / r["dossier"])
        return r
    except Exception:
        return {"nom_utilisateur": "", "bulletin_seuils": {}, "fuseau": "Europe/Paris"}


def chaine(raw: Path):
    """Le registre d'intégrité : chaque lot fermé a son empreinte et celle du précédent. Renvoie la liste des défauts."""
    defauts, precedent = [], "genese"
    for x in jsonl(raw / ".chaine.jsonl"):
        f = raw / x.get("fichier", "")
        if x.get("precedent") != precedent:
            defauts.append(f"{x.get('fichier')} : maillon précédent incorrect")
        if not f.exists():
            defauts.append(f"{x.get('fichier')} : fichier absent")
        elif "sha256:" + hashlib.sha256(f.read_bytes()).hexdigest() != x.get("sha256"):
            defauts.append(f"{x.get('fichier')} : contenu modifié après fermeture")
        precedent = x.get("sha256")
    return defauts


def couverture(mem: Path, utilisateur: str, jours: set, consolides: set):
    """Messages de l'utilisateur (≥ 6 mots) des lots CONSOLIDÉS de ces jours, et combien sont cités par un fait."""
    cites = set()
    for p in (mem / "pages").glob("*.md"):
        for l in p.read_text(encoding="utf-8").splitlines():
            s = SRC.search(l)
            for ref in (s.group(1).split(",") if s else []):
                r = REF.search(ref)
                if r:
                    cites |= {(r.group(1), k) for k in range(int(r.group(2)), int(r.group(3) or r.group(2)) + 1)}
    total = couverts = 0
    for f in sorted((mem / "raw").glob("20*.md")):
        if f.name[:10] not in jours or f.name not in consolides:
            continue
        courant = None
        lignes = f.read_text(encoding="utf-8").splitlines() + ["[00:00 fin]"]
        for n, l in enumerate(lignes, 1):
            m = ENTETE.match(l)
            if m:
                if courant and len(courant[2].split()) >= 6:
                    total += 1
                    couverts += any((f.name, k) in cites for k in range(courant[0], courant[1] + 1))
                courant = [n, n, m.group(3)] if m.group(2) == utilisateur else None
            elif courant is not None and l.strip() and not l.startswith(("<!--", "#", "---")):
                courant[1] = n; courant[2] += " " + l.strip()
    return total, couverts


def bulletin(mem: Path, jour: date, utilisateur: str, seuils: dict, version: str):
    """[(niveau, indicateur, texte)] — niveau : vert, orange, rouge, info."""
    out = []
    raw = mem / "raw"
    hier = jour - timedelta(days=1)
    fenetre = {(jour - timedelta(days=k)).isoformat() for k in range(1, 8)}
    # 1. intégrité du brut
    d = chaine(raw)
    out.append(("rouge", "intégrité", "; ".join(d[:3]) + (f" (+{len(d) - 3})" if len(d) > 3 else ""))
               if d else ("vert", "intégrité", f"{len(jsonl(raw / '.chaine.jsonl'))} lots fermés, chaîne intacte"))
    # 2. lots en attente
    consolides = {x.get("fichier") for x in jsonl(raw / ".consolide.jsonl")}
    attente = [x for x in jsonl(raw / ".chaine.jsonl") if x.get("fichier") not in consolides]
    vieux = []
    for x in attente:
        try:
            age = datetime.now().astimezone() - datetime.fromisoformat(x["ferme_le"])
            if age.total_seconds() > 3600 * seuils["attente_heures"]:
                vieux.append(x["fichier"])
        except (KeyError, ValueError):
            vieux.append(x.get("fichier"))
    out.append(("rouge", "consolidation", f"{len(vieux)} lot(s) fermé(s) jamais consolidé(s) : {', '.join(vieux[:3])}")
               if vieux else ("vert", "consolidation", f"aucun lot en retard ({len(attente)} en cours)"))
    # 3. dernière consolidation, rejets sur 7 jours
    passages = [x for x in jsonl(mem / "telemetrie" / "consolidations.jsonl") if str(x.get("ts", ""))[:10] in fenetre]
    if passages and passages[-1].get("statut") not in ("ok", "vide", "rien"):
        out.append(("rouge", "dernier passage", f"statut « {passages[-1].get('statut')} » le {passages[-1].get('ts', '')[:16]}"))
    retenus = sum(x.get("faits_retenus") or 0 for x in passages)
    rejetes = sum(x.get("fragments_rejetes") or 0 for x in passages)
    modeles = sorted({x.get("modele") for x in passages if x.get("modele")})
    # 4. couverture sur 7 jours
    total, couverts = couverture(mem, utilisateur, fenetre, consolides)
    if total < seuils["messages_min"]:
        out.append(("info", "couverture 7 j", f"{couverts}/{total} messages — trop peu pour juger"))
    else:
        c = 100 * couverts / total
        niv = "rouge" if c < seuils["couverture_rouge"] else "orange" if c < seuils["couverture_orange"] else "vert"
        out.append((niv, "couverture 7 j", f"{c:.0f} % de tes messages retenus ({couverts}/{total}), seuil {seuils['couverture_orange']:.0f} %"))
    if retenus + rejetes:
        t = 100 * rejetes / (retenus + rejetes)
        niv = ("info" if total < seuils["messages_min"] else
               "rouge" if t > seuils["rejets_rouge"] else "orange" if t > seuils["rejets_orange"] else "vert")
        out.append((niv, "refus 7 j", f"{t:.0f} % ({rejetes} refusés, {retenus} retenus ; {len(passages)} passages, {', '.join(modeles) or '?'})"))
    # 5. compteurs de la veille : s'il y a eu des échanges hier, le fichier du jour doit exister
    ecrit_hier = any(f.name.startswith(hier.isoformat()) for f in raw.glob("20*.md"))
    tele = mem / "telemetrie" / f"{hier.isoformat()}.json"
    if ecrit_hier and not tele.exists():
        out.append(("orange", "compteurs", f"pas de compteurs pour le {hier.isoformat()} alors qu'il y a eu des échanges"))
    elif tele.exists():
        t = json.loads(tele.read_text(encoding="utf-8"))
        niv = "orange" if t.get("erreurs") else "vert"
        out.append((niv, "compteurs", f"hier : {t.get('tours_ecrits', 0)} tours écrits, {t.get('erreurs', 0)} erreur(s), "
                                      f"{t.get('secrets_refuses', 0)} secret(s) refusé(s), {t.get('retraits', 0)} retrait(s)"))
    # 6. souvenirs qui remontent (phase 2) : échecs d'hier
    rappels = jsonl(mem / "rappel" / f"{hier.isoformat()}.jsonl")
    echecs = sum(1 for x in rappels if x.get("statut") == "echec")
    if rappels:
        out.append(("orange" if echecs else "vert", "rappel", f"hier : {len(rappels)} recherches de souvenirs, {echecs} échec(s)"))
    # 7. le graphe
    try:
        g = json.loads((mem / "graphe" / "rapport.json").read_text(encoding="utf-8"))
        niv = "rouge" if g.get("statut") not in ("ok", None) else "orange" if g.get("alerte") else "vert"
        out.append((niv, "graphe", g.get("alerte") or f"{g.get('noeuds')} nœuds, {g.get('faits')} faits, {g.get('aretes')} liens"))
    except (OSError, ValueError):
        out.append(("orange", "graphe", "rapport du graphe illisible"))
    out.append(("info", "version", version or "?"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--complet", action="store_true", help="imprimer tout le bulletin, même vert")
    ap.add_argument("--memoire", help="dossier de la mémoire (défaut : celui de l'agent)")
    ap.add_argument("--jour", help="AAAA-MM-JJ : le bulletin de ce matin-là (défaut : aujourd'hui)")
    ap.add_argument("--utilisateur", help="étiquette de l'utilisateur dans le brut (défaut : nom_utilisateur des réglages)")
    a = ap.parse_args()
    r = reglages()
    mem = Path(a.memoire or r.get("_memoire") or "/opt/data/memoire")
    seuils = {**SEUILS, **{k: v for k, v in (r.get("bulletin_seuils") or {}).items() if k in SEUILS}}
    try:
        version = re.search(r"^version:\s*(\S+)", (Path(__file__).resolve().parents[1] / "plugin.yaml").read_text(encoding="utf-8"), re.M).group(1)
    except (OSError, AttributeError):
        version = ""
    jour = date.fromisoformat(a.jour) if a.jour else date.today()
    lignes = bulletin(mem, jour, (a.utilisateur or r.get("nom_utilisateur") or "").lower(), seuils, version)
    alerte = [x for x in lignes if x[0] in ("orange", "rouge")]
    if not alerte and not a.complet:
        return 0
    pastille = {"vert": "🟢", "orange": "🟠", "rouge": "🔴", "info": "·"}
    titre = "🔴 Mémoire : à regarder" if any(x[0] == "rouge" for x in alerte) else "🟠 Mémoire : à surveiller" if alerte else "🟢 Mémoire : tout va bien"
    print(f"{titre} — bulletin du {jour.strftime('%d/%m/%Y')}")
    for niv, quoi, texte in (lignes if a.complet else alerte):
        print(f"{pastille[niv]} {quoi} : {texte}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
