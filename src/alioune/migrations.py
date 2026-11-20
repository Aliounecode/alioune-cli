"""Création de fichiers de migration Alembic, sans base de données ni import d'Alembic."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path

from alioune.moteur import rendre_texte
from alioune.noms import en_snake_case
from alioune.plan import ErreurPlan

DOSSIER_VERSIONS = Path("alembic") / "versions"

_MOTIF_REVISION = re.compile(r"""^revision\s*(?::[^=\n]+)?=\s*["']([^"']+)["']""", re.M)
_MOTIF_PRECEDENTE = re.compile(r"""^down_revision\s*(?::[^=\n]+)?=\s*(.+)$""", re.M)


def tete_actuelle(racine: Path) -> str | None:
    """Identifiant de la dernière migration (None s'il n'y en a pas encore)."""
    revisions: set[str] = set()
    precedentes: set[str] = set()
    dossier = racine / DOSSIER_VERSIONS
    for fichier in dossier.glob("*.py") if dossier.is_dir() else []:
        texte = fichier.read_text(encoding="utf-8")
        revision = _MOTIF_REVISION.search(texte)
        if revision is None:
            continue
        revisions.add(revision.group(1))
        precedente = _MOTIF_PRECEDENTE.search(texte)
        if precedente:
            precedentes.update(re.findall(r"""["']([^"']+)["']""", precedente.group(1)))
    tetes = revisions - precedentes
    if len(tetes) > 1:
        raise ErreurPlan(
            "Plusieurs têtes de migration détectées (" + ", ".join(sorted(tetes)) + "). "
            "Fusionne-les avec « alembic merge heads » avant de générer une migration."
        )
    return next(iter(tetes), None)


def indenter(lignes: list[str], espaces: int = 4) -> str:
    marge = " " * espaces
    return "\n".join(f"{marge}{ligne}" if ligne else "" for ligne in lignes)


def preparer_migration(
    racine: Path,
    message: str,
    lignes_upgrade: list[str],
    lignes_downgrade: list[str],
    maintenant: datetime | None = None,
) -> tuple[Path, str]:
    """Retourne (chemin relatif, contenu) d'une migration chaînée à la tête actuelle."""
    maintenant = maintenant or datetime.now()
    revision = uuid.uuid4().hex[:12]
    precedente = tete_actuelle(racine)
    contenu = rendre_texte(
        "generer/migration.py.j2",
        {
            "message": message,
            "revision": revision,
            "precedente": precedente,
            "date": maintenant.isoformat(sep=" ", timespec="microseconds"),
            "corps_upgrade": indenter(lignes_upgrade or ["pass"]),
            "corps_downgrade": indenter(lignes_downgrade or ["pass"]),
        },
    )
    nom_fichier = (
        f"{maintenant:%Y_%m_%d_%H%M}-{revision}_{en_snake_case(message)[:50]}.py"
    )
    return DOSSIER_VERSIONS / nom_fichier, contenu


def lignes_creation_table(
    nom_table: str,
    colonnes: list[str],
    index: list[tuple[str, str, bool]] | None = None,
    contraintes: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Construit les lignes `upgrade` / `downgrade` d'une création de table.

    `colonnes` : lignes de code `sa.Column(...)`. `index` : (nom, colonne, unique).
    `contraintes` : lignes de code `sa.ForeignKeyConstraint(...)` ajoutées après la clé primaire.
    """
    upgrade = [
        "op.create_table(",
        f'    "{nom_table}",',
        '    sa.Column("id", sa.Integer(), nullable=False),',
        *[f"    {colonne}," for colonne in colonnes],
        '    sa.Column("cree_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),',
        '    sa.Column("modifie_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),',
        '    sa.PrimaryKeyConstraint("id"),',
        *[f"    {contrainte}," for contrainte in contraintes or []],
        ")",
    ]
    downgrade: list[str] = []
    for nom_index, colonne, unique in index or []:
        upgrade.append(
            f'op.create_index(op.f("{nom_index}"), "{nom_table}", ["{colonne}"], unique={unique})'
        )
        downgrade.append(f'op.drop_index(op.f("{nom_index}"), table_name="{nom_table}")')
    downgrade.append(f'op.drop_table("{nom_table}")')
    return upgrade, downgrade


def lignes_table_association(
    nom: str, proprietaire: tuple[str, str], cible: tuple[str, str]
) -> tuple[list[str], list[str]]:
    """Lignes `upgrade` / `downgrade` d'une table d'association plusieurs-à-plusieurs.

    `proprietaire` et `cible` : (colonne, table visée) de chaque côté. Les liens sont supprimés
    en cascade quand l'un des deux éléments disparaît.
    """
    (col_a, table_a), (col_b, table_b) = proprietaire, cible
    haut = [
        "op.create_table(",
        f'    "{nom}",',
        f'    sa.Column("{col_a}", sa.Integer(), nullable=False),',
        f'    sa.Column("{col_b}", sa.Integer(), nullable=False),',
        f'    sa.ForeignKeyConstraint(["{col_a}"], ["{table_a}.id"], ondelete="CASCADE"),',
        f'    sa.ForeignKeyConstraint(["{col_b}"], ["{table_b}.id"], ondelete="CASCADE"),',
        f'    sa.PrimaryKeyConstraint("{col_a}", "{col_b}"),',
        ")",
    ]
    return haut, [f'op.drop_table("{nom}")']
