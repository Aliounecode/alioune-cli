"""Aide pour retrouver un projet alioune et son environnement virtuel."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

FICHIER_MARQUEUR = "alioune.json"


def trouver_racine(depart: Path | None = None) -> Path | None:
    """Remonte depuis `depart` jusqu'au dossier contenant `alioune.json`."""
    courant = (depart or Path.cwd()).resolve()
    for dossier in [courant, *courant.parents]:
        if (dossier / FICHIER_MARQUEUR).is_file():
            return dossier
    return None


def lire_configuration(racine: Path) -> dict:
    return json.loads((racine / FICHIER_MARQUEUR).read_text(encoding="utf-8"))


def python_du_venv(racine: Path) -> Path | None:
    """Chemin de l'interpréteur du `.venv` du projet, s'il existe."""
    sous_dossier, executable = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
    chemin = racine / ".venv" / sous_dossier / executable
    return chemin if chemin.is_file() else None


def python_a_utiliser(racine: Path) -> tuple[str, bool]:
    """Retourne (interpréteur, venv_trouvé)."""
    venv = python_du_venv(racine)
    if venv is not None:
        return str(venv), True
    return sys.executable, False
