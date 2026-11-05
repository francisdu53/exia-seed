#!/bin/sh
# Banc 17 — quel modèle pour consolider ? (docs/17). La mémoire vivante de Nexa n'est que LUE.
#   sh lancer.sh installer                 # dossier du banc, copie figée du plugin de production, code du banc
#   sh lancer.sh preparer                  # les six points de départ (sans réseau, mémoire montée en lecture seule)
#   sh lancer.sh consolider <modèle> <r1|r2>   # gpt-6-astra : dans le conteneur de Nexa (son abonnement)
#   sh lancer.sh mesurer                   # couverture, questions, lecteur et juge (Terra), bilan
#   FACTICE=1 sh lancer.sh …               # tout le banc sans réseau ni dépense
# Le banc vit dans le dossier de travail de Nexa (pour qu'Astra y écrive) : $HERMES_HOME/workspace/banc-modeles
set -e
ICI=$(cd "$(dirname "$0")" && pwd)
HOTE=$HERMES_HOME/workspace/banc-modeles
DANS_NEXA=/opt/data/workspace/banc-modeles
SRC=$HERMES_HOME/memoire
IMG=${IMG:-nexa-hermes:0.21.3-20260915}
ETAPE=$1; shift || true
case "$ETAPE" in
  installer)
    mkdir -p $HOTE/code $HOTE/appels
    [ -e $HOTE/plugin/exia_seed ] || { mkdir -p $HOTE/plugin; cp -a $HERMES_HOME/plugins/exia_seed $HOTE/plugin/; rm -rf $HOTE/plugin/exia_seed/__pycache__; }
    cp $ICI/*.py $HOTE/code/
    chown -R 10000:10000 $HOTE; chmod 700 $HOTE
    echo "banc installé : $HOTE (plugin figé : $(ls $HOTE/plugin/exia_seed | wc -l) fichiers)";;
  preparer)
    docker run --rm --network none -u 10000:10000 -e TZ=Europe/Paris -v $SRC:/src:ro -v $HOTE:/banc -v $ICI:/code:ro \
      --entrypoint /opt/hermes/.venv/bin/python3 $IMG /code/preparer.py 2>&1 | grep -v -E "WARNING|warn\(";;
  consolider)
    M=$1; R=$2
    cp $ICI/*.py $HOTE/code/; chown -R 10000:10000 $HOTE/code
    if [ "$M" = gpt-6-astra ]; then
      docker exec -u hermes -e BANC=$DANS_NEXA ${FACTICE:+-e BANC_FACTICE=1} -e TZ=Europe/Paris nexa \
        /opt/hermes/.venv/bin/python3 $DANS_NEXA/code/consolider.py "$M" "$R"
    else
      # root dans le conteneur jetable : les clés sont en 600 (root) et ne sont copiées nulle part ; fichiers rendus à Nexa ensuite
      docker run --rm -u 0 -e TZ=Europe/Paris ${FACTICE:+-e BANC_FACTICE=1} ${PLAFOND:+-e BANC_PLAFOND_USD=$PLAFOND} \
        ${SORTIE_MAX:+-e BANC_SORTIE_MAX=$SORTIE_MAX} ${NOUVEL_ESSAI:+-e BANC_NOUVEL_ESSAI=1} \
        -v $HOTE:/banc -v $ICI:/code:ro -v $HOME/banc-locomo/.cle-openai:/cle-openai:ro -v <exia-ghost>/.env:/cles/ghost.env:ro \
        --entrypoint /opt/hermes/.venv/bin/python3 $IMG /code/consolider.py "$M" "$R" 2>&1 | grep -v -E "WARNING|warn\("
      chown -R 10000:10000 $HOTE
    fi;;
  mesurer)
    docker run --rm -u 0 -e TZ=Europe/Paris ${FACTICE:+-e BANC_FACTICE=1} ${PLAFOND:+-e BANC_PLAFOND_USD=$PLAFOND} \
      -e LOCOMO_BANC=/banc -e LOCOMO_RUN=mesures-17 ${MESURES:+-e BANC_MESURES=$MESURES} ${PASSAGES:+-e BANC_PASSAGES=$PASSAGES} \
      -v $HOTE:/banc -v $ICI:/code:ro -v $ICI/../locomo:/locomo:ro -v $ICI/../longmemeval:/lme:ro \
      -v $HOME/banc-locomo/.cle-openai:/cle-openai:ro -v <exia-ghost>/.env:/cles/ghost.env:ro \
      --entrypoint /opt/hermes/.venv/bin/python3 $IMG /code/mesurer.py "$@" 2>&1 | grep -v -E "WARNING|warn\("
    chown -R 10000:10000 $HOTE;;
  *) echo "étape inconnue : $ETAPE"; exit 1;;
esac
