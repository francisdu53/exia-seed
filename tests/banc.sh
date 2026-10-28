#!/bin/sh
# Banc d'essai EXIA SEED — un conteneur JETABLE par suite : sans réseau, image de production de
# Nexa, dossier de données vierge, vrai chargeur de plugins d'Hermès. Rien ne touche la mémoire
# vivante de Nexa.
#
#   sh tests/banc.sh                              # toutes les suites
#   sh tests/banc.sh test_R2_temps.py             # une suite
#   PLUGIN=/chemin/exia_seed sh tests/banc.sh     # tester une autre copie du plugin (ex. celle de production)
#   REF=/chemin/exia_seed_0.8.0 sh tests/banc.sh test_langues.py   # + comparaison octet à octet avec une référence
#
# Consigné dans le dépôt le 26/09/2026 : jusque-là cette configuration de test ne vivait que dans
# l'historique d'une conversation, et sa perte a d'abord fait croire à une régression.
IMG=${IMG:-nexa-hermes:0.21.3-20260915}
TESTS=$(cd "$(dirname "$0")" && pwd)
# Par défaut : le plugin DU DÉPÔT (16/10 : visait jusque-là la copie de production du VPS, introuvable ailleurs)
PLUGIN=${PLUGIN:-$TESTS/../plugin/exia_seed}
[ $# -eq 0 ] && set -- $(cd "$TESTS" && ls test_*.py)
echec=0
for t in "$@"; do
  D=$(mktemp -d /tmp/banc-exia-seed.XXXXXX); mkdir -p "$D/plugins"; cp -r "$PLUGIN" "$D/plugins/exia_seed"
  rm -rf "$D/plugins/exia_seed/__pycache__"
  # REF=/chemin/exia_seed : une version de référence, montée en plugins/exia_seed_ref (non-régression stricte, test_langues.py)
  [ -n "$REF" ] && cp -r "$REF" "$D/plugins/exia_seed_ref" && rm -rf "$D/plugins/exia_seed_ref/__pycache__"
  cat > "$D/config.yaml" <<'CFG'
timezone: Europe/Paris
memory:
  provider: exia_seed
  exia_seed:
    nom_utilisateur: francis
    nom_agent: nexa
    seuil_lot_tokens: 1000        # petit seuil : la rotation des lots se teste en deux messages
    consolidation_auto: false     # les suites déclenchent la consolidation elles-mêmes
CFG
  chown -R 10000:10000 "$D"
  echo "════ $t"
  docker run --rm --network none -u 10000:10000 -e HERMES_HOME=/opt/data -e TZ=Europe/Paris \
    -v "$D":/opt/data -v "$TESTS":/tests:ro -w /opt/data --entrypoint /opt/hermes/.venv/bin/python3 \
    "$IMG" "/tests/$t" 2>&1 | grep -v -E "WARNING|warn\(" || echec=1
  rm -rf "$D"
done
exit $echec
