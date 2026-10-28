#!/bin/sh
# Banc LongMemEval (docs/13) — les étapes du banc LoCoMo (consolider, fusionner, chercher, embeddings) + celles de
# LongMemEval (répondre, juger, bilan), chaque étape dans un conteneur JETABLE de l'image de Nexa.
#
#   RUN=oracle sh lancer.sh preparer <ids…> [--fils 8]   # consolidation (modèle)
#   RUN=oracle sh lancer.sh fusionner | recuperer         # sans modèle
#   RUN=oracle sh lancer.sh embeddings                    # moteur B, sur l'HÔTE
#   RUN=oracle sh lancer.sh repondre_lme | juger_lme | bilan_lme
#   FACTICE=1 : modèle factice, conteneur sans réseau.   PLAFOND=10 : arrêt local à 10 $ cumulés pour ce run.
set -e
ICI=$(cd "$(dirname "$0")" && pwd)
LOCOMO=$ICI/../locomo
BANC=${BANC:-$HOME/banc-longmemeval}
RUN=${RUN:-oracle}
IMG=${IMG:-nexa-hermes:0.21.3-20260915}
PLUGIN=${PLUGIN:-$ICI/../../plugin/exia_seed}
DONNEES=${DONNEES:-/banc/donnees/lme_oracle_locomo.json}
CLE=${CLE:-$HOME/banc-locomo/.cle-openai}
ETAPE=$1; shift
ENV_JEU="-e LOCOMO_ROLES=agent -e LOCOMO_HOMONYMES=0 -e LOCOMO_IMPLICITES=1 ${CONSOLIDATION:+-e LOCOMO_CONSOLIDATION=$CONSOLIDATION}"
if [ "$ETAPE" = embeddings ]; then
  DONNEES_HOTE=$(echo "$DONNEES" | sed "s#^/banc#$BANC#")
  cd "$LOCOMO" && env LOCOMO_BANC="$BANC" LOCOMO_RUN="$RUN" LOCOMO_DONNEES="$DONNEES_HOTE" LOCOMO_ROLES=agent LOCOMO_HOMONYMES=0 \
    LOCOMO_IMPLICITES=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 nice -n 10 ${PYTHON_EMBEDDINGS:-python3} embeddings.py "$@" 2>&1 \
    | grep -v -i -E "warn|Loading weights"
  exit 0
fi
case "$ETAPE" in *_lme) DOSSIER=/lme ;; *) DOSSIER=/locomo ;; esac
RESEAU=""; MONTAGE_CLE=""
if [ "$FACTICE" = 1 ]; then RESEAU="--network none"; else MONTAGE_CLE="-v $CLE:/cle-openai:ro -e LOCOMO_CLE=/cle-openai"; fi
docker run --rm $RESEAU -u 0 -e PYTHONDONTWRITEBYTECODE=1 -e TZ=UTC -e LOCOMO_BANC=/banc -e LOCOMO_RUN="$RUN" \
  -e LOCOMO_FACTICE="${FACTICE:-0}" -e LOCOMO_DONNEES="$DONNEES" ${MODELE:+-e LOCOMO_MODELE=$MODELE} \
  ${PLAFOND:+-e LOCOMO_PLAFOND_USD=$PLAFOND} $ENV_JEU $MONTAGE_CLE \
  -v "$BANC":/banc -v "$LOCOMO":/locomo:ro -v "$ICI":/lme:ro -v "$PLUGIN":/plugins/exia_seed:ro -w "$DOSSIER" \
  --entrypoint /opt/hermes/.venv/bin/python3 "$IMG" "$DOSSIER/$ETAPE.py" "$@" 2>&1 | grep -v -E "WARNING|warn\("
