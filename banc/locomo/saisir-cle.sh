#!/bin/sh
# Saisie de la clé API OpenAI pour le banc LoCoMo — À LANCER PAR FRANCIS LUI-MÊME, dans un terminal SSH :
#     sh $HOME/banc-locomo/saisir-cle.sh
# La clé est tapée masquée, écrite dans $HOME/banc-locomo/.cle-openai (droits 600, root seul), jamais affichée.
# Claude ne la lit jamais : seul le banc la lit, au moment d'appeler l'API.
set -e
F=$HOME/banc-locomo/.cle-openai
printf "Clé API OpenAI (commence par sk-, saisie masquée) : "
stty -echo; read -r CLE; stty echo; echo
case "$CLE" in sk-*) ;; *) echo "Ce n'est pas une clé OpenAI (elle doit commencer par sk-). Rien n'est écrit."; exit 1;; esac
umask 077
printf "%s\n" "$CLE" > "$F"
chmod 600 "$F"
echo "Clé enregistrée dans $F (600). Longueur : ${#CLE} caractères."
