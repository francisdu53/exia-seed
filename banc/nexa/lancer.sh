#!/bin/sh
# Banc « consolidation exhaustive » sur la mémoire de Nexa (docs/13 §19) : COPIE de son historique fermé, reconsolidée
# dans un conteneur jetable, sans réseau vers Nexa, sans aucun de ses secrets. Sa mémoire vivante n'est que LUE (cp).
#   sh lancer.sh copier                     # copie les lots fermés + chaîne + registre dans les deux runs
#   VARIANTE=selective|exhaustive sh lancer.sh reconsolider
#   sh lancer.sh <script>.py [args]         # autres étapes du banc (mesures)
set -e
ICI=$(cd "$(dirname "$0")" && pwd)
BANC=${BANC:-$HOME/banc-nexa-exh}
SRC=$HERMES_HOME/memoire
IMG=${IMG:-nexa-hermes:0.21.3-20260915}
ETAPE=$1; shift || true
if [ "$ETAPE" = copier ]; then
  for v in selective exhaustive; do
    M=$BANC/runs/$v/memoire; [ -e "$M" ] && { echo "$M existe déjà"; exit 1; }
    mkdir -p $M/raw $M/pages
    find $SRC/raw -maxdepth 1 -name "*.md" ! -name "*_open.md" -exec cp {} $M/raw/ \;
    cp $SRC/raw/.chaine.jsonl $BANC/runs/$v/chaine_complete.jsonl     # versée jour par jour par reconsolider.py
    [ -f $SRC/raw/.retraits.jsonl ] && cp $SRC/raw/.retraits.jsonl $M/raw/ || true
    cp $SRC/registre.md $M/; echo "fr" > $M/.langue
    echo "$v : $(ls $M/raw/*.md | wc -l) lots, $(wc -l < $BANC/runs/$v/chaine_complete.jsonl) dans la chaîne complète"
  done
  chown -R 10000:10000 $BANC; exit 0
fi
[ "$ETAPE" = reconsolider ] && ETAPE=reconsolider.py
docker run --rm -u 0 -e PYTHONDONTWRITEBYTECODE=1 -e TZ=Europe/Paris -e LOCOMO_BANC=/banc -e LOCOMO_RUN="${VARIANTE:-exhaustive}" \
  ${PLAFOND:+-e LOCOMO_PLAFOND_USD=$PLAFOND} ${NEXA_RUNS:+-e NEXA_RUNS=$NEXA_RUNS} ${VARIANTE:+-e LOCOMO_CONSOLIDATION=$( [ "$VARIANTE" = selective ] && echo selective )} \
  -v $HOME/banc-locomo/.cle-openai:/cle-openai:ro -e LOCOMO_CLE=/cle-openai \
  -v "$BANC":/banc -v "$ICI/../locomo":/locomo:ro -v "$ICI":/nexa:ro -v "$ICI/../longmemeval":/lme:ro -v "$ICI/../../plugin/exia_seed":/plugins/exia_seed:ro -w /nexa \
  --entrypoint /opt/hermes/.venv/bin/python3 "$IMG" "/nexa/$ETAPE" "$@" 2>&1 | grep -v -E "WARNING|warn\("
