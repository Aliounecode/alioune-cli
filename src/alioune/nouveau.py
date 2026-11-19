"""Logique de la commande `alioune new`."""

from __future__ import annotations

import secrets
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from alioune import __version__
from alioune.moteur import rendre_arborescence
from alioune.noms import en_snake_case, nom_affichage
from alioune.projet import python_du_venv


class ErreurCreation(Exception):
    """Erreur lisible à afficher à l'utilisateur."""


@dataclass
class ResultatCreation:
    racine: Path
    fichiers: list[Path]
    venv_cree: bool
    git_initialise: bool


def _executer(commande: list[str], cwd: Path) -> None:
    resultat = subprocess.run(commande, cwd=cwd, capture_output=True, text=True)
    if resultat.returncode != 0:
        fin = "\n".join((resultat.stdout + resultat.stderr).strip().splitlines()[-15:])
        raise ErreurCreation(f"Échec de : {' '.join(commande)}\n{fin}")


def creer_projet(
    nom: str,
    base: str,
    installer: bool,
    initialiser_git: bool,
    dossier_parent: Path,
) -> ResultatCreation:
    racine = dossier_parent / nom
    if racine.exists() and any(racine.iterdir()):
        raise ErreurCreation(f"Le dossier « {racine} » existe déjà et n'est pas vide.")

    contexte = {
        "nom_projet": nom,
        "nom_affichage": nom_affichage(nom),
        "nom_base": en_snake_case(nom),
        "base": base,
        "version_alioune": __version__,
    }

    racine.mkdir(parents=True, exist_ok=True)

    fichiers = rendre_arborescence("projet", racine, contexte)
    _ecrire_env_reel(racine)
    fichiers.append(Path(".env"))

    venv_cree = False
    if installer:
        _executer([sys.executable, "-m", "venv", ".venv"], cwd=racine)
        python = python_du_venv(racine)
        if python is None:
            raise ErreurCreation("L'environnement virtuel a été créé mais son Python est introuvable.")
        _executer(
            [str(python), "-m", "pip", "install", "--disable-pip-version-check", "-q",
             "-r", "requirements-dev.txt"],
            cwd=racine,
        )
        venv_cree = True

    git_initialise = False
    if initialiser_git and shutil.which("git"):
        _executer(["git", "init", "-q"], cwd=racine)
        git_initialise = True

    return ResultatCreation(racine, fichiers, venv_cree, git_initialise)


def _ecrire_env_reel(racine: Path) -> None:
    """Écrit `.env` depuis `.env.example` en y mettant une vraie clé secrète."""
    exemple = (racine / ".env.example").read_text(encoding="utf-8")
    reel = exemple.replace("changez-moi", secrets.token_urlsafe(48))
    (racine / ".env").write_text(reel, encoding="utf-8", newline="\n")
