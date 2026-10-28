import json, sys
from collections import Counter
B = "$HERMES_HOME/workspace/banc-souvenirs/"
for v in sys.argv[1:]:
    X = [json.loads(s) for s in open(B + f"variante_{v}.jsonl")]
    c = Counter(p for x in X for p, _ in x["montre"])
    print(f"{v:12}", " · ".join(f"{p.split('.')[0][:22]} {c[p]}" for p in ("plateforme-donnees-meteo.md", "jev.md", "delegation-assistant.md", "controle-documents-assistant.md")))
