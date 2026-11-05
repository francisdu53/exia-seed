#!/usr/bin/env python3
"""Les six points de départ du banc 17 (docs/17 §3) — la mémoire de Nexa TELLE QU'ELLE ÉTAIT LA VEILLE de chaque jour.

Conteneur jetable, sans réseau ; la mémoire vivante est montée en LECTURE SEULE (/src) ; tout est écrit sous /banc.
Pour un jour J :
- pages : un fait est gardé si TOUTES ses sources (lignes du brut, notes du registre) sont antérieures à J ; une page
  sans fait gardé disparaît ; fiches d'identité et mots distinctifs retirés partout (ils peuvent contenir l'avenir) ;
- brut : les seuls lots FERMÉS du jour J, et leurs lignes de la chaîne d'intégrité, dans l'ordre ; rien n'est consolidé ;
- registre : complet ; toutes les notes sont marquées intégrées SAUF celles du jour J (en attente, comme cette nuit-là) ;
- thésaurus copié tel quel (non daté : limite connue, la même pour tous les modèles) ; graphe recalculé.

    python3 preparer.py
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "/banc/plugin")
from exia_seed import graphe as G                                      # noqa: E402
from exia_seed import pages as P                                       # noqa: E402

SRC, BANC = Path("/src"), Path("/banc")
# Les six jours (étiquette → date) vivent dans un fichier PRIVÉ du banc, jamais dans le dépôt (docs/17 §8)
PANEL = os.environ.get("BANC_PANEL", "jours")                          # jours.json : panel 1 ; panel2.json : confirmation (§11)
JOURS = json.loads((BANC / f"{PANEL}.json").read_text(encoding="utf-8"))
_RE_REG = re.compile(r"^## (\d{4}-\d\d-\d\d) [\d:]+ — (\w+) · ")
_RE_RAW = re.compile(r"raw/(\d{4}-\d\d-\d\d)_")
_RE_SRC = re.compile(r"(?:^| )src:(\S+)")


def dates_registre():
    d = {}
    for l in (SRC / "registre.md").read_text(encoding="utf-8").splitlines():
        m = _RE_REG.match(l)
        if m:
            d[m.group(2)] = m.group(1)
    return d


def dates_sources(meta: str, reg):
    """Les jours de toutes les sources d'un fait ; None si une source est introuvable (le fait n'est pas gardé)."""
    m = _RE_SRC.search(meta or "")
    if not m:
        return None
    jours = []
    for ref in m.group(1).split(","):
        r = _RE_RAW.search(ref)
        if r:
            jours.append(r.group(1))
        elif ref.startswith("registre:") and ref[9:] in reg:
            jours.append(reg[ref[9:]])
        else:
            return None
    return jours or None


def preparer(etiq: str, jour: str, reg) -> dict:
    dest = BANC / "depart" / etiq / "memoire"
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "raw").mkdir(parents=True); (dest / "pages").mkdir()
    # brut du jour J (lots fermés) et leur chaîne, dans l'ordre
    chaine = [l for l in (SRC / "raw" / ".chaine.jsonl").read_text(encoding="utf-8").splitlines()
              if l.strip() and json.loads(l)["fichier"].startswith(jour)]
    lots = [json.loads(l)["fichier"] for l in chaine]
    for f in lots:
        shutil.copy2(SRC / "raw" / f, dest / "raw" / f)
    (dest / "raw" / ".chaine.jsonl").write_text("".join(l + "\n" for l in chaine), encoding="utf-8")
    if (SRC / "raw" / ".retraits.jsonl").exists():
        shutil.copy2(SRC / "raw" / ".retraits.jsonl", dest / "raw" / ".retraits.jsonl")
    # registre : seules les notes du jour J restent à intégrer
    shutil.copy2(SRC / "registre.md", dest / "registre.md")
    attente = sorted(i for i, d in reg.items() if d == jour)
    (dest / "registre.integre.jsonl").write_text(
        "".join(json.dumps({"id": i, "page": "", "lot": "depart-banc-17"}) + "\n" for i, d in sorted(reg.items()) if d != jour),
        encoding="utf-8")
    for f in ("thesaurus.json", ".langue"):
        if (SRC / f).exists():
            shutil.copy2(SRC / f, dest / f)
    if not (dest / ".langue").exists():
        (dest / ".langue").write_text("fr\n", encoding="utf-8")
    # pages de la veille
    gardes = retires = pages = 0
    for p in P.lister(SRC / "pages"):
        sections = {}
        for cle, lignes in p.sections.items():
            garde = []
            for l in lignes:
                meta = P._RE_META.search(l)
                jours = dates_sources(meta.group(1) if meta else "", reg)
                if jours and max(jours) < jour:
                    garde.append(l)
                else:
                    retires += 1
            sections[cle] = garde
        n = sum(len(v) for v in sections.values())
        if not n:
            continue
        entete = {k: v for k, v in p.entete.items() if k not in ("summary", "summary_date", "keywords")}
        P.Page(dest / "pages" / p.chemin.name, entete, sections).ecrire()
        gardes += n; pages += 1
    r = G.calculer(dest, implicites=("francis", "nexa"))
    return {"jour": jour, "lots": len(lots), "notes_en_attente": len(attente), "pages": pages, "faits_gardes": gardes,
            "faits_retires": retires, "graphe": {k: r.get(k) for k in ("statut", "noeuds", "aretes")}}


def main():
    reg = dates_registre()
    bilan = {etiq: preparer(etiq, jour, reg) for etiq, jour in JOURS.items()}
    (BANC / "depart" / f"bilan-{PANEL}.json").write_text(json.dumps(bilan, indent=1, ensure_ascii=False), encoding="utf-8")
    for etiq, b in bilan.items():
        print(etiq, json.dumps(b, ensure_ascii=False))


if __name__ == "__main__":
    main()
