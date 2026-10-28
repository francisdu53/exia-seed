#!/bin/sh
# Banc LoCoMo (docs/09) — chaque étape dans un conteneur JETABLE (image de Nexa), jamais dans celui de Nexa.
# Données de travail : $HOME/banc-locomo (hors du volume de Nexa). Plugin : la 0.9.0 du dépôt, en lecture seule.
#
#   RUN=pilote sh lancer.sh preparer conv-26 conv-30      # consolidation (modèle)
#   RUN=pilote sh lancer.sh fusionner                     # échelle F (sans modèle)
#   RUN=pilote sh lancer.sh recuperer                     # moteurs A et C (sans modèle)
#   RUN=pilote sh lancer.sh embeddings                    # moteur B, sur l'HÔTE
#   RUN=pilote sh lancer.sh repondre [A B C D E]          # réponses (modèle)
#   RUN=pilote sh lancer.sh juger                         # juge (modèle)
#   RUN=pilote sh lancer.sh bilan
#
#   FACTICE=1 : modèle factice, conteneur SANS RÉSEAU (aucun appel ne peut partir) — pour éprouver le banc.
#   DONNEES=/banc/donnees/autre.json : un autre jeu (le jeu à blanc des tests).
set -e
ICI=$(cd "$(dirname "$0")" && pwd)
BANC=${BANC:-$HOME/banc-locomo}
RUN=${RUN:-pilote}
IMG=${IMG:-nexa-hermes:0.21.3-20260915}
PLUGIN=${PLUGIN:-$ICI/../../plugin/exia_seed}
ETAPE=$1; shift
if [ "$ETAPE" = embeddings ] || [ "$ETAPE" = f1 ]; then
  DONNEES_HOTE=$(echo "${DONNEES:-/banc/donnees/locomo10.json}" | sed "s#^/banc#$BANC#")
  cd "$ICI" && env LOCOMO_BANC="$BANC" LOCOMO_RUN="$RUN" LOCOMO_DONNEES="$DONNEES_HOTE" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    nice -n 10 ${PYTHON_EMBEDDINGS:-python3} "$ETAPE.py" "$@" 2>&1 \
    | grep -v -i -E "warn|Loading weights"
  exit 0
fi
RESEAU=""
[ "$FACTICE" = 1 ] && RESEAU="--network none"
docker run --rm $RESEAU -u 0 -e PYTHONDONTWRITEBYTECODE=1 -e TZ=UTC -e LOCOMO_BANC=/banc -e LOCOMO_RUN="$RUN" \
  -e LOCOMO_FACTICE="${FACTICE:-0}" ${DONNEES:+-e LOCOMO_DONNEES=$DONNEES} ${MODELE:+-e LOCOMO_MODELE=$MODELE} \
  ${PLAFOND:+-e LOCOMO_PLAFOND_USD=$PLAFOND} ${POIDS_SUJET:+-e LOCOMO_POIDS_SUJET=$POIDS_SUJET} \
  ${ATTENUATION:+-e LOCOMO_ATTENUATION=$ATTENUATION} \
  -v "$BANC":/banc -v "$ICI":/locomo:ro -v "$PLUGIN":/plugins/exia_seed:ro -w /locomo \
  --entrypoint /opt/hermes/.venv/bin/python3 "$IMG" "/locomo/$ETAPE.py" "$@" 2>&1 | grep -v -E "WARNING|warn\("
