"""Utilitaires de nommage."""

from __future__ import annotations

import keyword
import re
import unicodedata

MOTIF_NOM_PROJET = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
MOTIF_NOM_CODE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def nom_projet_valide(nom: str) -> bool:
    return bool(MOTIF_NOM_PROJET.match(nom))


def nom_code_valide(nom: str) -> bool:
    """Nom utilisable pour un modèle, un service, un routeur... (avant conversion)."""
    return bool(MOTIF_NOM_CODE.match(nom)) and not keyword.iskeyword(en_snake_case(nom))


def en_snake_case(nom: str) -> str:
    """'Ma Boutique-en.ligne' / 'MaBoutique' -> 'ma_boutique...' (sans accents)."""
    sans_accents = (
        unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode("ascii")
    )
    separe = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", sans_accents)
    return re.sub(r"[^a-zA-Z0-9]+", "_", separe).strip("_").lower()


def en_pascal_case(nom: str) -> str:
    """'ligne_commande' -> 'LigneCommande'."""
    return "".join(mot.capitalize() for mot in en_snake_case(nom).split("_") if mot)


def nom_affichage(nom: str) -> str:
    """'ma-boutique_en.ligne' -> 'Ma Boutique En Ligne'."""
    return " ".join(mot.capitalize() for mot in re.split(r"[-_.\s]+", nom) if mot)


def pluriel_francais(nom_snake: str) -> str:
    """Pluriel simple du premier mot (nom + complément : ligne_commande -> lignes_commande).

    Les exceptions (festival, noms composés atypiques...) se corrigent avec --pluriel.
    """
    premier, *suite = nom_snake.split("_")
    if premier.endswith(("s", "x", "z")):
        pluriel = premier
    elif premier.endswith("al"):
        pluriel = premier[:-2] + "aux"
    elif premier.endswith(("au", "eu")):
        pluriel = premier + "x"
    else:
        pluriel = premier + "s"
    return "_".join([pluriel, *suite])
