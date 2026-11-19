"""Plan d'écriture : décrit ce qu'une commande va créer ou modifier, puis l'applique.

Séparer le « quoi » du « écrire » permet `--simuler` (dry-run) et de vérifier
les conflits avant de toucher au moindre fichier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class ErreurPlan(Exception):
    """Erreur lisible à afficher à l'utilisateur."""


@dataclass
class Insertion:
    """Ajoute `ligne` dans `chemin`, juste avant `marqueur` (ou en fin de fichier)."""

    chemin: Path
    ligne: str
    marqueur: str | None = None
    # Si une ligne commence déjà par `cle` (ex. « PYJWT » ou « CLOUDINARY_CLE_API= »),
    # on considère l'insertion comme déjà faite.
    cle: str | None = None


@dataclass
class Plan:
    creations: list[tuple[Path, str]] = field(default_factory=list)
    creations_si_absent: list[tuple[Path, str]] = field(default_factory=list)
    insertions: list[Insertion] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)


@dataclass
class Rapport:
    crees: list[Path] = field(default_factory=list)
    modifies: list[Path] = field(default_factory=list)
    inchanges: list[Path] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)


def appliquer(plan: Plan, racine: Path, *, ecraser: bool = False, simuler: bool = False) -> Rapport:
    """Applique le plan. Aucun fichier n'est écrit si un conflit est détecté."""
    conflits = [
        chemin for chemin, _ in plan.creations if (racine / chemin).exists()
    ]
    if conflits and not ecraser:
        liste = "\n".join(f"  - {chemin.as_posix()}" for chemin in conflits)
        raise ErreurPlan(
            f"Ces fichiers existent déjà (utilise --force pour les remplacer) :\n{liste}"
        )

    rapport = Rapport(avertissements=list(plan.avertissements))

    for chemin, contenu in plan.creations:
        rapport.crees.append(chemin)
        if not simuler:
            _ecrire(racine / chemin, contenu)

    for chemin, contenu in plan.creations_si_absent:
        if (racine / chemin).exists():
            continue
        rapport.crees.append(chemin)
        if not simuler:
            _ecrire(racine / chemin, contenu)

    # Les insertions lisent l'état « après création » ; en simulation on lit le disque tel quel.
    for insertion in plan.insertions:
        cible = racine / insertion.chemin
        if not cible.exists():
            rapport.avertissements.append(
                f"{insertion.chemin.as_posix()} est introuvable : ajoute à la main « {insertion.ligne} »."
            )
            continue
        texte = cible.read_text(encoding="utf-8")
        lignes = texte.splitlines()
        deja_present = insertion.ligne in lignes or (
            insertion.cle is not None
            and any(l.lower().startswith(insertion.cle.lower()) for l in lignes)
        )
        if deja_present:
            rapport.inchanges.append(insertion.chemin)
            continue
        if insertion.marqueur is None:
            nouveau = [*lignes, insertion.ligne]
        else:
            index = next((i for i, l in enumerate(lignes) if l.strip() == insertion.marqueur), None)
            if index is None:
                rapport.avertissements.append(
                    f"Marqueur « {insertion.marqueur} » absent de {insertion.chemin.as_posix()} : "
                    f"ajoute à la main « {insertion.ligne} »."
                )
                continue
            nouveau = [*lignes[:index], insertion.ligne, *lignes[index:]]
        if insertion.chemin not in rapport.modifies:
            rapport.modifies.append(insertion.chemin)
        if not simuler:
            cible.write_text("\n".join(nouveau) + "\n", encoding="utf-8", newline="\n")
    return rapport


def _ecrire(chemin: Path, contenu: str) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu, encoding="utf-8", newline="\n")
