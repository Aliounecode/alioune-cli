"""Logique de `alioune generate` : construit un Plan pour chaque type de fichier."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from alioune.migrations import lignes_creation_table, preparer_migration
from alioune.moteur import rendre_texte
from alioune.noms import en_pascal_case, en_snake_case, nom_code_valide, pluriel_francais
from alioune.plan import ErreurPlan, Insertion, Plan

MARQUEUR_MODELES = "# --- alioune:modeles ---"
MARQUEUR_IMPORTS = "# --- alioune:imports ---"
MARQUEUR_INCLUSIONS = "# --- alioune:inclusions ---"

CHEMIN_MODELES_INIT = Path("app/modeles/__init__.py")
CHEMIN_ROUTEURS_INIT = Path("app/routeurs/__init__.py")

NOMS_RESERVES = {"base", "__init__"}
CHAMPS_RESERVES = {"id", "cree_le", "modifie_le"}

# type -> (annotation Python, colonne SQLAlchemy, colonne en migration)
TYPES: dict[str, tuple[str, str, str]] = {
    "str": ("str", "String(255)", "sa.String(length=255)"),
    "text": ("str", "Text", "sa.Text()"),
    "int": ("int", "Integer", "sa.Integer()"),
    "float": ("float", "Float", "sa.Float()"),
    "decimal": ("Decimal", "Numeric(12, 2)", "sa.Numeric(precision=12, scale=2)"),
    "bool": ("bool", "Boolean", "sa.Boolean()"),
    "date": ("date", "Date", "sa.Date()"),
    "datetime": ("datetime", "DateTime(timezone=True)", "sa.DateTime(timezone=True)"),
}


# Valeurs d'exemple (JSON) utilisées par les tests générés.
EXEMPLES: dict[str, str] = {
    "str": '"exemple"',
    "text": '"texte d\'exemple"',
    "int": "1",
    "float": "1.5",
    "decimal": '"10.50"',
    "bool": "True",
    "date": '"2026-01-15"',
    "datetime": '"2026-01-15T10:00:00Z"',
}


@dataclass(frozen=True)
class Champ:
    nom: str
    type: str
    nullable: bool = False

    @property
    def py(self) -> str:
        return TYPES[self.type][0]

    @property
    def annotation(self) -> str:
        return f"{self.py} | None" if self.nullable else self.py

    @property
    def defaut(self) -> str:
        return " = None" if self.nullable else ""

    @property
    def colonne(self) -> str:
        return TYPES[self.type][1]

    @property
    def colonne_migration(self) -> str:
        return TYPES[self.type][2]

    @property
    def exemple(self) -> str:
        return EXEMPLES[self.type]

    @property
    def nom_sqlalchemy(self) -> str:
        return self.colonne.split("(")[0]


def analyser_champs(texte: str | None, defaut: str = "nom:str") -> list[Champ]:
    """'nom:str,prix:decimal,description:text?' -> [Champ, ...]."""
    brut = (texte or "").strip() or defaut
    champs: list[Champ] = []
    for element in re.split(r"[,\s]+", brut):
        if not element:
            continue
        nom, _, type_brut = element.partition(":")
        type_brut = type_brut or "str"
        nullable = type_brut.endswith("?")
        type_champ = type_brut.rstrip("?").lower()
        nom = en_snake_case(nom)
        if not nom or not re.fullmatch(r"[a-z][a-z0-9_]*", nom):
            raise ErreurPlan(f"Nom de champ invalide : « {element} ».")
        if nom in CHAMPS_RESERVES:
            raise ErreurPlan(f"Le champ « {nom} » est ajouté automatiquement : retire-le de --champs.")
        if type_champ not in TYPES:
            raise ErreurPlan(
                f"Type « {type_champ} » inconnu pour « {nom} ». Types disponibles : {', '.join(TYPES)}."
            )
        if any(c.nom == nom for c in champs):
            raise ErreurPlan(f"Le champ « {nom} » est répété.")
        champs.append(Champ(nom, type_champ, nullable))
    return champs


def _imports_stdlib(champs: list[Champ], avec_datetime: bool = False) -> str:
    """Lignes d'import de la bibliothèque standard nécessaires aux champs (ou chaîne vide)."""
    types_date = {c.py for c in champs if c.py in {"date", "datetime"}}
    if avec_datetime:
        types_date.add("datetime")
    lignes = []
    if types_date:
        lignes.append(f"from datetime import {', '.join(sorted(types_date))}")
    if any(c.py == "Decimal" for c in champs):
        lignes.append("from decimal import Decimal")
    return "\n".join(lignes)


def construire_contexte(nom: str, texte_champs: str | None, pluriel: str | None,
                        champs_par_defaut: str = "nom:str") -> dict:
    if not nom_code_valide(nom):
        raise ErreurPlan(
            f"Nom invalide : « {nom} ». Utilise des lettres, chiffres, tirets ou underscores "
            "(sans mot réservé de Python)."
        )
    snake = en_snake_case(nom)
    if snake in NOMS_RESERVES:
        raise ErreurPlan(f"« {snake} » est un nom réservé : choisis-en un autre.")
    nom_pluriel = en_snake_case(pluriel) if pluriel else pluriel_francais(snake)
    champs = analyser_champs(texte_champs, champs_par_defaut)
    return {
        "nom_snake": snake,
        "nom_classe": en_pascal_case(snake),
        "nom_pluriel": nom_pluriel,
        "nom_table": nom_pluriel,
        "nom_libelle": snake.replace("_", " ").capitalize(),
        "pluriel_libelle": nom_pluriel.replace("_", " ").capitalize(),
        "pluriel_url": nom_pluriel.replace("_", "-"),
        "champs": champs,
        "prefixe_env": snake.upper(),
        "protege": False,
        "a_champ_obligatoire": any(not c.nullable for c in champs),
    }


# --- Générateurs unitaires -------------------------------------------------

def _fichier_modele(ctx: dict) -> tuple[Path, str]:
    imports_sa = sorted({c.nom_sqlalchemy for c in ctx["champs"]})
    contenu = rendre_texte("generer/modele.py.j2", {
        **ctx,
        "imports_stdlib": _imports_stdlib(ctx["champs"]),
        "imports_sqlalchemy": ", ".join(imports_sa),
    })
    return Path(f"app/modeles/{ctx['nom_snake']}.py"), contenu


def _fichier_schema(ctx: dict) -> tuple[Path, str]:
    contenu = rendre_texte("generer/schema.py.j2", {
        **ctx, "imports_stdlib": _imports_stdlib(ctx["champs"], avec_datetime=True),
    })
    return Path(f"app/schemas/{ctx['nom_snake']}.py"), contenu


def _fichier_service(ctx: dict) -> tuple[Path, str]:
    return Path(f"app/services/{ctx['nom_snake']}.py"), rendre_texte("generer/service.py.j2", ctx)


def _fichier_routeur(ctx: dict) -> tuple[Path, str]:
    return Path(f"app/routeurs/{ctx['nom_snake']}.py"), rendre_texte("generer/routeur.py.j2", ctx)


def _fichier_test(ctx: dict) -> tuple[Path, str]:
    return Path(f"tests/test_{ctx['nom_pluriel']}.py"), rendre_texte("generer/test.py.j2", ctx)


def _fichier_migration(racine: Path, ctx: dict) -> tuple[Path, str]:
    colonnes = [
        f'sa.Column("{c.nom}", {c.colonne_migration}, nullable={c.nullable})' for c in ctx["champs"]
    ]
    haut, bas = lignes_creation_table(ctx["nom_table"], colonnes)
    return preparer_migration(racine, f"creer_table_{ctx['nom_table']}", haut, bas)


def _inscrire_modele(plan: Plan, ctx: dict) -> None:
    plan.insertions.append(Insertion(
        CHEMIN_MODELES_INIT,
        f"from app.modeles.{ctx['nom_snake']} import {ctx['nom_classe']}  # noqa: F401",
        MARQUEUR_MODELES,
    ))


def _inscrire_routeur(plan: Plan, ctx: dict) -> None:
    snake = ctx["nom_snake"]
    plan.insertions.append(Insertion(
        CHEMIN_ROUTEURS_INIT,
        f"from app.routeurs.{snake} import routeur as routeur_{snake}",
        MARQUEUR_IMPORTS,
    ))
    plan.insertions.append(Insertion(
        CHEMIN_ROUTEURS_INIT, f"routeur_api.include_router(routeur_{snake})", MARQUEUR_INCLUSIONS,
    ))


def _verifier_presence(racine: Path, plan: Plan, chemins: list[tuple[Path, str]]) -> None:
    """Avertit si un fichier dont dépend ce qu'on génère n'existe pas (et n'est pas dans le plan)."""
    prevus = {chemin for chemin, _ in plan.creations}
    for chemin, commande in chemins:
        if chemin not in prevus and not (racine / chemin).exists():
            plan.avertissements.append(
                f"{chemin.as_posix()} n'existe pas : génère-le avec « alioune g {commande} »."
            )


# --- Point d'entrée --------------------------------------------------------

TYPES_GENERATION = ("ressource", "modele", "schema", "service", "routeur", "migration", "config")


def preparer_generation(
    racine: Path,
    type_generation: str,
    nom: str,
    champs: str | None = None,
    pluriel: str | None = None,
    protege: bool = False,
) -> Plan:
    defaut = "cle_api:str" if type_generation == "config" else "nom:str"
    ctx = construire_contexte(nom, champs, pluriel, defaut)
    plan = Plan()

    if protege:
        if not (racine / "app/dependances.py").exists():
            raise ErreurPlan("--protege demande l'authentification : lance d'abord « alioune auth ».")
        ctx["protege"] = True

    snake = ctx["nom_snake"]

    if type_generation == "ressource":
        plan.creations += [
            _fichier_modele(ctx), _fichier_schema(ctx), _fichier_service(ctx),
            _fichier_routeur(ctx), _fichier_migration(racine, ctx), _fichier_test(ctx),
        ]
        _inscrire_modele(plan, ctx)
        _inscrire_routeur(plan, ctx)

    elif type_generation == "modele":
        plan.creations.append(_fichier_modele(ctx))
        _inscrire_modele(plan, ctx)

    elif type_generation == "schema":
        plan.creations.append(_fichier_schema(ctx))

    elif type_generation == "service":
        plan.creations.append(_fichier_service(ctx))
        _verifier_presence(racine, plan, [
            (Path(f"app/modeles/{snake}.py"), f"modele {snake}"),
            (Path(f"app/schemas/{snake}.py"), f"schema {snake}"),
        ])

    elif type_generation == "routeur":
        plan.creations.append(_fichier_routeur(ctx))
        _inscrire_routeur(plan, ctx)
        _verifier_presence(racine, plan, [
            (Path(f"app/modeles/{snake}.py"), f"modele {snake}"),
            (Path(f"app/schemas/{snake}.py"), f"schema {snake}"),
            (Path(f"app/services/{snake}.py"), f"service {snake}"),
        ])

    elif type_generation == "migration":
        plan.creations.append(preparer_migration(racine, nom, [], []))

    elif type_generation == "config":
        plan.creations.append((
            Path(f"app/configurations/{snake}.py"),
            rendre_texte("generer/config.py.j2", {
                **ctx, "imports_stdlib": _imports_stdlib(ctx["champs"]),
            }),
        ))
        plan.creations_si_absent.append((Path("app/configurations/__init__.py"), '"""Configurations des services externes."""\n'))
        for fichier in (".env.example", ".env"):
            for champ in ctx["champs"]:
                variable = f"{ctx['prefixe_env']}_{champ.nom.upper()}="
                plan.insertions.append(Insertion(Path(fichier), variable, cle=variable))

    else:
        raise ErreurPlan(f"Type inconnu : « {type_generation} ». Types : {', '.join(TYPES_GENERATION)}.")

    return plan
