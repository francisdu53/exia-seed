#!/usr/bin/env python3
"""Banc 17 §22 (+ §28 : python3 decouper.py echange [panel]) — les paliers de lots : chaque lot en attente d'une journée, découpé aux frontières des messages en
morceaux de K tokens au plus (comme si un lot se fermait à K tokens). `depart/` n'est pas touché ; le résultat va dans
`depart-K/`. Les lignes retirées par l'utilisateur sont écartées (elles ne sont jamais montrées au modèle).

    python3 decouper.py 3000 [panel]
"""
import json, os, re, shutil, sys
from pathlib import Path
BANC = Path(os.environ.get("BANC", "/banc"))
# 12/11/2026 (§28) : K = "echange" → un lot par échange (un message de l'utilisateur + les réponses qui suivent) ;
# §29 : "echange3c2" → 3 échanges par lot + les 2 échanges précédents en CONTEXTE (non citable), dans la chaîne
_m = re.fullmatch(r"echange(?:(\d+)c(\d+))?", sys.argv[1])
ECHANGE = bool(_m); N_ECH = int(_m.group(1) or 1) if _m else 1; N_CTX = int(_m.group(2) or 0) if _m else 0
K = 0 if ECHANGE else int(sys.argv[1])
NOM_K = sys.argv[1] if ECHANGE else str(K)
AGENT = os.environ.get("BANC_AGENT", "nexa")
PANEL = sys.argv[2] if len(sys.argv) > 2 else "jours"
JOURS = json.loads((BANC / f"{PANEL}.json").read_text())
ENTETE = re.compile(r"^\[\d\d:\d\d [a-z_]+\]")
tok = lambda s: len(s) // 4 + 1
for j in JOURS:
    src = BANC / "depart" / j / "memoire"; dst = BANC / f"depart-{NOM_K}" / j / "memoire"
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(src, dst)
    raw = dst / "raw"
    faits = {json.loads(l)["fichier"] for l in (raw / ".consolide.jsonl").read_text().splitlines() if l.strip()} if (raw / ".consolide.jsonl").exists() else set()
    retraits = {}
    if (raw / ".retraits.jsonl").exists():
        for l in (raw / ".retraits.jsonl").read_text().splitlines():
            r = json.loads(l); a, b = r["lignes"]; retraits.setdefault(r["fichier"], set()).update(range(int(a), int(b) + 1))
    chaine = [json.loads(l) for l in (raw / ".chaine.jsonl").read_text().splitlines() if l.strip()]
    nouvelle, n_lots = [], 0
    for e in chaine:
        f = e["fichier"]
        if f in faits or not (raw / f).exists():
            nouvelle.append(e); continue
        texte = (raw / f).read_text(encoding="utf-8").splitlines()
        i = texte.index("## Échanges") if "## Échanges" in texte else len(texte)
        tete = texte[:i]
        messages, cour = [], []
        for n, l in enumerate(texte[i + 1:], start=i + 2):
            if n in retraits.get(f, set()) or not l.strip() or l.lstrip().startswith("<!--"):
                continue
            if ENTETE.match(l) and cour:
                messages.append(cour); cour = []
            cour.append(l)
        if cour: messages.append(cour)
        morceaux, contextes, m, t = [], [], [], 0
        if ECHANGE:                                   # échanges = un message de l'utilisateur + ce qui suit
            ech = []
            for msg in messages:
                parle = ENTETE.match(msg[0]).group(0)[7:-1] if ENTETE.match(msg[0]) else ""
                if not ech or parle != AGENT: ech.append([])
                ech[-1] += msg
            for i in range(0, len(ech), N_ECH):
                morceaux.append([l for e in ech[i:i + N_ECH] for l in e])
                contextes.append([l for e in ech[max(0, i - N_CTX):i] for l in e] if N_CTX else [])
            messages = []
        for msg in messages:
            c = sum(tok(x) for x in msg)
            parle = ENTETE.match(msg[0]).group(0)[7:-1] if ENTETE.match(msg[0]) else ""
            if m and ((ECHANGE and parle != AGENT) or (not ECHANGE and t + c > K)):
                morceaux.append(m); m, t = [], 0
            m += msg; t += c
        if m: morceaux.append(m)
        (raw / f).unlink()
        for k, mm in enumerate(morceaux, 1):
            nom = f.replace(".md", f"-{k:02d}.md")
            (raw / nom).write_text("\n".join(tete + ["## Échanges", ""] + mm) + "\n", encoding="utf-8")
            ctx = contextes[k - 1] if contextes else []
            nouvelle.append({**e, "fichier": nom, "tokens": sum(tok(x) for x in mm), "decoupe_de": f,
                             **({"contexte": ctx} if ctx else {})}); n_lots += 1
    (raw / ".chaine.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in nouvelle), encoding="utf-8")
    if (raw / ".retraits.jsonl").exists():
        (raw / ".retraits.jsonl").unlink()                      # déjà appliqués au découpage
    print(f"{j} : {n_lots} lots de {K} tokens au plus")
