"""Logique de `alioune auth` : installe l'authentification (JWT) dans un projet."""

from __future__ import annotations

from pathlib import Path

from alioune.generateurs import (
    CHEMIN_MODELES_INIT,
    CHEMIN_ROUTEURS_INIT,
    MARQUEUR_IMPORTS,
    MARQUEUR_INCLUSIONS,
    MARQUEUR_MODELES,
)
from alioune.migrations import lignes_creation_table, preparer_migration
from alioune.moteur import rendre_en_memoire
from alioune.plan import Insertion, Plan

DEPENDANCES = [
    ("pyjwt>=2.8", "pyjwt"),
    ("pwdlib[argon2]>=0.2", "pwdlib"),
    ("email-validator>=2.1", "email-validator"),
    ("python-multipart>=0.0.9", "python-multipart"),
]


def preparer_auth(racine: Path) -> Plan:
    plan = Plan()
    plan.creations += rendre_en_memoire("auth", {})

    colonnes = [
        'sa.Column("email", sa.String(length=255), nullable=False)',
        'sa.Column("nom_complet", sa.String(length=255), nullable=False)',
        'sa.Column("mot_de_passe_hache", sa.String(length=255), nullable=False)',
        'sa.Column("role", sa.String(length=50), nullable=False)',
        'sa.Column("est_actif", sa.Boolean(), nullable=False)',
    ]
    haut, bas = lignes_creation_table(
        "utilisateurs", colonnes, index=[("ix_utilisateurs_email", "email", True)]
    )
    plan.creations.append(preparer_migration(racine, "creer_table_utilisateurs", haut, bas))

    plan.insertions += [
        Insertion(
            CHEMIN_MODELES_INIT,
            "from app.modeles.utilisateur import Utilisateur  # noqa: F401",
            MARQUEUR_MODELES,
        ),
        Insertion(
            CHEMIN_ROUTEURS_INIT,
            "from app.routeurs.auth import routeur as routeur_auth",
            MARQUEUR_IMPORTS,
        ),
        Insertion(
            CHEMIN_ROUTEURS_INIT, "routeur_api.include_router(routeur_auth)", MARQUEUR_INCLUSIONS
        ),
    ]
    for ligne, cle in DEPENDANCES:
        plan.insertions.append(Insertion(Path("requirements.txt"), ligne, cle=cle))
    return plan
