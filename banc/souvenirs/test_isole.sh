#!/bin/sh
# Étape 4 (docs/11) — une COPIE JETABLE de Nexa répond à un vrai message de Francis, en phase 1 puis en phase 2.
#
#   sh test_isole.sh <phase 1|2> <instantané mémoire> <fichier message> <étiquette>
#
# Copie : configuration, accès au modèle (auth.json), SOUL.md, AGENTS.md actuel, compétences, notes, mémoires
# natives, et la mémoire EXIA SEED TELLE QU'ELLE ÉTAIT juste avant le message (instantané git du banc). Aucun
# autre secret (.env, jeton Google, boîte mail : non copiés). Outils : file, skills, memory + les 3 outils
# d'EXIA SEED — PAS de terminal, de web, de Google ni de courriel : rien ne peut agir hors de la copie.
# Consolidation automatique coupée. La copie (et son auth.json) est détruite à la fin.
set -e
PHASE=$1; INST=$2; MSG=$3; NOM=$4
SRC=$HERMES_HOME
B=$HERMES_HOME/workspace/banc-souvenirs
T=$(mktemp -d "$(dirname "$HERMES_HOME")"/staging/test-isole.XXXXXX)
D=$T/data; mkdir -p $D/plugins $D/workspace/courses-app
cp $SRC/config.yaml $SRC/auth.json $SRC/SOUL.md $SRC/AGENTS.md $SRC/models_dev_cache.json $SRC/context_length_cache.yaml $D/ 2>/dev/null || true
[ -n "$AGENTS" ] && cp "$AGENTS" $D/AGENTS.md          # AGENTS=… : une autre version (ex. celle d'avant l'incident)
cp -r $SRC/skills $SRC/knowledge $SRC/memories $D/
cp $SRC/workspace/courses-app/README.md $D/workspace/courses-app/ 2>/dev/null || true
cp -r "$(dirname "$HERMES_HOME")"/staging/exia_seed $D/plugins/exia_seed; rm -rf $D/plugins/exia_seed/__pycache__
cp -r $B/instantanes/$INST $D/memoire; rm -rf $D/memoire/rappel $D/memoire/requetes
python3 - "$D/config.yaml" "$PHASE" <<'EOF'
import sys, yaml
f, phase = sys.argv[1], int(sys.argv[2])
c = yaml.safe_load(open(f)) or {}
m = c.setdefault("memory", {}).setdefault("exia_seed", {})
m["phase"] = phase; m["consolidation_auto"] = False
yaml.safe_dump(c, open(f, "w"), allow_unicode=True, sort_keys=False)
EOF
cp "$MSG" $D/message.txt
chown -R 10000:10000 $T
docker run --rm -u 10000:10000 -e HERMES_HOME=/opt/data -e TZ=Europe/Paris -v $D:/opt/data -w /opt/data \
  --entrypoint /opt/hermes/.venv/bin/hermes nexa-hermes:0.21.3-20260915 \
  chat --query-file /opt/data/message.txt --oneshot -Q -t file,skills,memory --max-turns 12 > $T/reponse.txt 2>$T/erreurs.txt || true
mkdir -p $B/isole
{ echo "=== $NOM · phase $PHASE · mémoire $INST"; echo "--- réponse"; cat $T/reponse.txt
  echo "--- outils utilisés"; grep -hoE "tool [a-z_]+ completed|Tool [a-z_]+ returned error" $D/logs/agent.log 2>/dev/null | sort | uniq -c
  echo "--- souvenirs joints"; cat $D/memoire/rappel/*.jsonl 2>/dev/null | python3 -c "import sys,json;[print(json.loads(l).get('injecte')) for l in sys.stdin]"
} > $B/isole/$NOM-phase$PHASE.txt
rm -rf $T
cat $B/isole/$NOM-phase$PHASE.txt | head -60
