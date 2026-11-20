"""Moteur de gabarits : transforme un dossier de gabarits en arborescence réelle.

Règles de nommage dans `gabarits/` :
- un fichier terminé par `.j2` est rendu avec Jinja2 (le suffixe disparaît) ;
- tout autre fichier est copié tel quel ;
- un nom commençant par `dot_` devient un nom caché (`dot_env` -> `.env`),
  ce qui évite que les fichiers cachés soient ignorés à l'empaquetage.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

DOSSIER_GABARITS = Path(__file__).resolve().parent / "gabarits"


def traduire_nom(nom: str) -> str:
    """Convertit un nom de gabarit en nom de fichier final."""
    if nom.endswith(".j2"):
        nom = nom[: -len(".j2")]
    if nom.startswith("dot_"):
        nom = "." + nom[len("dot_"):]
    return nom


def _environnement(source: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(source)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )


def rendre_texte(gabarit_fichier: str, contexte: dict[str, Any]) -> str:
    """Rend un seul gabarit (chemin relatif à `gabarits/`, ex. `generer/modele.py.j2`).

    Pour un fichier Python, les suites de lignes vides sont ramenées à deux au plus et le
    fichier se termine par un seul saut de ligne (les conditions Jinja en laissent parfois trop).
    """
    contenu = _environnement(DOSSIER_GABARITS).get_template(gabarit_fichier).render(**contexte)
    if gabarit_fichier.endswith(".py.j2"):
        contenu = re.sub(r"\n{4,}", "\n\n\n", contenu).rstrip("\n") + "\n"
    return contenu


def rendre_en_memoire(gabarit: str, contexte: dict[str, Any]) -> list[tuple[Path, str]]:
    """Comme `rendre_arborescence`, mais sans rien écrire : retourne (chemin relatif, contenu)."""
    source = DOSSIER_GABARITS / gabarit
    environnement = _environnement(source)
    resultat: list[tuple[Path, str]] = []
    for chemin in sorted(source.rglob("*")):
        if chemin.is_dir() or "__pycache__" in chemin.parts:
            continue
        relatif = chemin.relative_to(source)
        final = Path(*[traduire_nom(partie) for partie in relatif.parts])
        if chemin.suffix == ".j2":
            contenu = environnement.get_template(relatif.as_posix()).render(**contexte)
        else:
            contenu = chemin.read_text(encoding="utf-8")
        resultat.append((final, contenu))
    return resultat


def rendre_arborescence(
    gabarit: str, destination: Path, contexte: dict[str, Any]
) -> list[Path]:
    """Génère dans `destination` tous les fichiers du gabarit `gabarit`.

    Retourne la liste des fichiers créés (chemins relatifs à `destination`).
    """
    source = DOSSIER_GABARITS / gabarit
    environnement = _environnement(source)

    crees: list[Path] = []
    for chemin in sorted(source.rglob("*")):
        if chemin.is_dir() or "__pycache__" in chemin.parts:
            continue
        relatif = chemin.relative_to(source)
        final = Path(*[traduire_nom(partie) for partie in relatif.parts])
        cible = destination / final
        cible.parent.mkdir(parents=True, exist_ok=True)

        if chemin.suffix == ".j2":
            contenu = environnement.get_template(relatif.as_posix()).render(**contexte)
            cible.write_text(contenu, encoding="utf-8", newline="\n")
        else:
            shutil.copyfile(chemin, cible)
        crees.append(final)
    return crees
