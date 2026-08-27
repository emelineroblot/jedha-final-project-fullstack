#!/usr/bin/env bash
# Crée l'environnement virtuel du projet et l'enregistre comme kernel Jupyter.
# Multi-plateforme : Windows (Git Bash), Linux et macOS.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

PYTHON="${PYTHON:-python}"
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON=python3

echo "→ Création de l'environnement virtuel dans .venv"
"$PYTHON" -m venv .venv

# Le venv place les binaires dans Scripts/ sous Windows, bin/ ailleurs.
if [ -f ".venv/Scripts/activate" ]; then
    VENV_BIN=".venv/Scripts"
else
    VENV_BIN=".venv/bin"
fi
# shellcheck disable=SC1090
source "$VENV_BIN/activate"

"$PYTHON" -m pip install --upgrade pip

if [ -f "config/requirements.lock.txt" ]; then
    echo "→ Installation depuis config/requirements.lock.txt"
    "$PYTHON" -m pip install -r config/requirements.lock.txt
else
    echo "→ Installation depuis requirements.txt"
    "$PYTHON" -m pip install -r requirements.txt
fi

# Le kernel porte le nom du PROJET, pas celui du dossier config/.
KERNEL_NAME="$(basename "$PROJECT_DIR")"
"$PYTHON" -m ipykernel install --user \
    --name "$KERNEL_NAME" --display-name "Python ($KERNEL_NAME)"

echo
echo "✅ Environnement prêt."
echo "   Activation : source $VENV_BIN/activate"
echo "   Kernel Jupyter : Python ($KERNEL_NAME)"
