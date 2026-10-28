import re, sys, math
from collections import Counter
from pathlib import Path
sys.path.insert(0, "/opt/data/workspace/banc-souvenirs/plugins")
from exia_seed import graphe as G
tours = []
for f in sorted(Path("/opt/data/memoire/raw").glob("*.md")):
    for bloc in re.split(r"\n(?=\[\d\d:\d\d \w+\])", f.read_text(encoding="utf-8")):
        m = re.match(r"\[\d\d:\d\d (\w+)\] (.*)", bloc, re.S)
        if m and m.group(1) == "francis": tours.append(set(G._norm(m.group(2)).split()))
N = len(tours); df = Counter(w for t in tours for w in t)
r = lambda w: math.log(1 + N / (1 + df[w])) / math.log(1 + N)
print("tours", N)
for groupe, ws in (("BRUIT", "donnees avant waiting model assistant place agent platform modele debosselage application outils liste autoplus echange delegation subagent still"),
                   ("UTILE", "email envoi memoire controle systeme destinataires controles golf agents existants documents courses facture factures")):
    print(groupe, " · ".join(f"{w} {df[w]} ({r(w):.2f})" for w in ws.split()))
