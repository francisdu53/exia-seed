#!/bin/sh
# EXIA SEED — consolidation de fin de journée (cron sans agent, 23h55 Paris).
# Ferme le lot de brut du jour et le range en pages. Silencieux si tout va bien : zéro token,
# aucune notification. Seule une anomalie est imprimée, donc livrée sur Telegram.
exec /opt/hermes/.venv/bin/python /opt/data/plugins/exia_seed/outils/consolider.py --forcer
