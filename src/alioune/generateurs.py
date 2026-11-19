"""Logique de `alioune generate` : construit un Plan pour chaque type de fichier."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from alioune.migrations import DOSSIER_VERSIONS, lignes_creation_table, preparer_migration
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

# fk  ou  fk(modele)  : relation vers un autre modèle (voir analyser_champs).
MOTIF_FK = re.compile(r"^fk(?:\(([a-z][a-z0-9_-]*)\))?$")


@dataclass(frozen=True)
class Champ:
    """Un champ de modèle. Pour une relation, `nom` est la colonne (ex. « categorie_id »)."""

    nom: str
    type: str
    nullable: bool = False
    cible: str | None = None         # relation : nom (snake_case) du modèle visé
    classe_cible: str | None = None  # relation : classe du modèle visé
    table_cible: str | None = None   # relation : table du modèle visé

    @property
    def est_fk(self) -> bool:
        return self.type == "fk"

    @property
    def relation(self) -> str:
        """Nom de l'attribut-relation (« categorie » pour « categorie_id »)."""
        return self.nom[: -len("_id")]

    @property
    def ondelete(self) -> str:
        # Facultative : si le parent disparaît, on garde l'élément. Obligatoire : on refuse.
        return "SET NULL" if self.nullable else "RESTRICT"

    @property
    def py(self) -> str:
        return "int" if self.est_fk else TYPES[self.type][0]

    @property
    def annotation(self) -> str:
        return f"{self.py} | None" if self.nullable else self.py

    @property
    def defaut(self) -> str:
        return " = None" if self.nullable else ""

    @property
    def colonne(self) -> str:
        if self.est_fk:
            return f'ForeignKey("{self.table_cible}.id", ondelete="{self.ondelete}"), index=True'
        return TYPES[self.type][1]

    @property
    def colonne_migration(self) -> str:
        return "sa.Integer()" if self.est_fk else TYPES[self.type][2]

    @property
    def exemple(self) -> str:
        return "1" if self.est_fk else EXEMPLES[self.type]

    @property
    def nom_sqlalchemy(self) -> str:
        return self.colonne.split("(")[0]


def _infos_modele(racine: Path | None, snake: str) -> tuple[str, str, bool]:
    """(classe, table, existe) du modèle `snake`, lus dans app/modeles/<snake>.py s'il existe."""
    classe, table = en_pascal_case(snake), pluriel_francais(snake)
    if racine is not None:
        fichier = racine / "app" / "modeles" / f"{snake}.py"
        if fichier.is_file():
            texte = fichier.read_text(encoding="utf-8")
            trouve_classe = re.search(r"^class\s+(\w+)\(", texte, re.M)
            trouve_table = re.search(r"""__tablename__\s*=\s*["'](\w+)["']""", texte)
            return (
                trouve_classe.group(1) if trouve_classe else classe,
                trouve_table.group(1) if trouve_table else table,
                True,
            )
    return classe, table, False


def analyser_champs(
    texte: str | None, defaut: str = "nom:str", racine: Path | None = None
) -> list[Champ]:
    """'nom:str,prix:decimal,note:text?,categorie:fk' -> [Champ, ...].

    Types : str text int float decimal bool date datetime ; `?` à la fin = facultatif.
    Relation : `categorie:fk` (colonne categorie_id vers le modèle « categorie »)
    ou `origine:fk(pays)` (colonne origine_id vers le modèle « pays »).
    """
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

        correspondance_fk = MOTIF_FK.match(type_champ)
        if correspondance_fk:
            base = nom[: -len("_id")] if nom.endswith("_id") and len(nom) > 3 else nom
            cible = en_snake_case(correspondance_fk.group(1) or base)
            classe, table, _ = _infos_modele(racine, cible)
            nom = f"{base}_id"
            champ = Champ(nom, "fk", nullable, cible, classe, table)
        elif type_champ in TYPES:
            champ = Champ(nom, type_champ, nullable)
        elif type_champ.startswith("fk"):
            raise ErreurPlan(
                f"Relation invalide : « {element} ». Syntaxe : categorie:fk, "
                "origine:fk(pays) ou origine:fk(pays)? (le ? va à la fin)."
            )
        else:
            raise ErreurPlan(
                f"Type « {type_champ} » inconnu pour « {nom} ». "
                f"Types disponibles : {', '.join(TYPES)}, fk."
            )

        if champ.nom in CHAMPS_RESERVES:
            raise ErreurPlan(f"Le champ « {champ.nom} » est ajouté automatiquement : retire-le de --champs.")
        if any(c.nom == champ.nom for c in champs):
            raise ErreurPlan(f"Le champ « {champ.nom} » est répété.")
        champs.append(champ)

    noms = {c.nom for c in champs}
    for champ in champs:
        if champ.est_fk and champ.relation in noms:
            raise ErreurPlan(
                f"Le nom « {champ.relation} » est utilisé à la fois par la relation et par un champ."
            )
    return champs


def _imports_stdlib(champs: list[Champ], avec_datetime: bool = False, avec_typing: bool = False) -> str:
    """Lignes d'import de la bibliothèque standard nécessaires aux champs (ou chaîne vide)."""
    types_date = {c.py for c in champs if c.py in {"date", "datetime"}}
    if avec_datetime:
        types_date.add("datetime")
    lignes = []
    if types_date:
        lignes.append(f"from datetime import {', '.join(sorted(types_date))}")
    if any(c.py == "Decimal" for c in champs):
        lignes.append("from decimal import Decimal")
    if avec_typing:
        lignes.append("from typing import TYPE_CHECKING")
    return "\n".join(lignes)


def _contexte_relations(racine: Path | None, snake: str, champs: list[Champ]) -> dict:
    """Informations sur les relations (modèles liés, URL, tests) utilisées par les gabarits."""
    relations = []
    cibles: dict[str, dict] = {}
    for champ in (c for c in champs if c.est_fk):
        if champ.cible == snake:
            raise ErreurPlan(
                "Une relation d'un modèle vers lui-même n'est pas générée automatiquement : "
                "génère le modèle, puis ajoute-la à la main."
            )
        relations.append({
            "attribut": champ.nom,
            "relation": champ.relation,
            "cible": champ.cible,
            "classe": champ.classe_cible,
            "table": champ.table_cible,
            "url": champ.table_cible.replace("_", "-"),
            "libelle": champ.cible.replace("_", " ").capitalize(),
            "nullable": champ.nullable,
        })
        cibles.setdefault(champ.cible, {
            "snake": champ.cible, "classe": champ.classe_cible, "table": champ.table_cible,
        })
    return {"relations": relations, "cibles": list(cibles.values())}


def construire_contexte(nom: str, texte_champs: str | None, pluriel: str | None,
                        champs_par_defaut: str = "nom:str", racine: Path | None = None) -> dict:
    if not nom_code_valide(nom):
        raise ErreurPlan(
            f"Nom invalide : « {nom} ». Utilise des lettres, chiffres, tirets ou underscores "
            "(sans mot réservé de Python)."
        )
    snake = en_snake_case(nom)
    if snake in NOMS_RESERVES:
        raise ErreurPlan(f"« {snake} » est un nom réservé : choisis-en un autre.")
    nom_pluriel = en_snake_case(pluriel) if pluriel else pluriel_francais(snake)
    champs = analyser_champs(texte_champs, champs_par_defaut, racine)
    obligatoires = [c.nom for c in champs if not c.nullable]
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
        "a_champ_obligatoire": bool(obligatoires),
        "champs_obligatoires": obligatoires,
        **_contexte_relations(racine, snake, champs),
    }


# --- Générateurs unitaires -------------------------------------------------

def _fichier_modele(ctx: dict) -> tuple[Path, str]:
    imports_sa = sorted({c.nom_sqlalchemy for c in ctx["champs"]})
    contenu = rendre_texte("generer/modele.py.j2", {
        **ctx,
        "imports_stdlib": _imports_stdlib(ctx["champs"], avec_typing=bool(ctx["relations"])),
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
    imports = ["from fastapi.testclient import TestClient"]
    if ctx.get("utilisateur_cible"):
        imports.insert(0, "import uuid\n")
    parents = [c for c in ctx["cibles"] if c["snake"] != "utilisateur"]
    if parents and not ctx["protege"]:
        imports.append("")
        imports += [
            f"from tests.test_{c['table']} import donnees_valides as donnees_{c['snake']}"
            for c in parents
        ]
    contenu = rendre_texte("generer/test.py.j2", {**ctx, "imports_test": "\n".join(imports)})
    return Path(f"tests/test_{ctx['nom_pluriel']}.py"), contenu


def _fichier_migration(racine: Path, ctx: dict) -> tuple[Path, str]:
    champs = ctx["champs"]
    colonnes = [
        f'sa.Column("{c.nom}", {c.colonne_migration}, nullable={c.nullable})' for c in champs
    ]
    contraintes = [
        f'sa.ForeignKeyConstraint(["{c.nom}"], ["{c.table_cible}.id"], ondelete="{c.ondelete}")'
        for c in champs if c.est_fk
    ]
    index = [(f"ix_{ctx['nom_table']}_{c.nom}", c.nom, False) for c in champs if c.est_fk]
    haut, bas = lignes_creation_table(ctx["nom_table"], colonnes, index, contraintes)
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


def _table_a_une_migration(racine: Path, table: str) -> bool:
    dossier = racine / DOSSIER_VERSIONS
    motif = re.compile(rf"""op\.create_table\(\s*["']{re.escape(table)}["']""")
    return any(
        motif.search(f.read_text(encoding="utf-8")) for f in dossier.glob("*.py")
    ) if dossier.is_dir() else False


def _verifier_relations(racine: Path, plan: Plan, ctx: dict) -> None:
    """Avertit si un modèle lié n'existe pas encore ou n'a pas de migration."""
    for cible in ctx["cibles"]:
        if not (racine / "app" / "modeles" / f"{cible['snake']}.py").exists():
            plan.avertissements.append(
                f"La relation vise « {cible['snake']} », qui n'existe pas encore : "
                f"génère-le d'abord avec « alioune g ressource {cible['snake']} » "
                "(sa migration doit précéder celle-ci)."
            )
        elif not _table_a_une_migration(racine, cible["table"]):
            plan.avertissements.append(
                f"La table « {cible['table']} » n'a pas de migration : "
                "alioune migrate échouera tant qu'elle n'est pas créée."
            )


def _preparer_tests(racine: Path, plan: Plan, ctx: dict) -> None:
    """Ajoute le fichier de tests si les tests des modèles liés permettent de l'écrire."""
    manquants: list[str] = []
    if not ctx["protege"]:
        for cible in ctx["cibles"]:
            if cible["snake"] == "utilisateur":
                continue
            test_parent = racine / "tests" / f"test_{cible['table']}.py"
            if not test_parent.is_file() or "def donnees_valides" not in test_parent.read_text(encoding="utf-8"):
                manquants.append(cible["snake"])
    if manquants:
        plan.avertissements.append(
            "Tests non générés : il manque tests/test_<modèle lié>.py avec donnees_valides() pour "
            + ", ".join(manquants) + " (génère le modèle lié avec « alioune g ressource »)."
        )
        return

    conftest = racine / "tests" / "conftest.py"
    base = "sqlite"
    marqueur = racine / "alioune.json"
    if marqueur.is_file():
        base = re.search(r'"base"\s*:\s*"(\w+)"', marqueur.read_text(encoding="utf-8")).group(1)
    cles_appliquees = base != "sqlite" or (
        conftest.is_file() and "foreign_keys" in conftest.read_text(encoding="utf-8")
    )
    restreinte = None
    for relation in ctx["relations"]:
        routeur_parent = racine / "app" / "routeurs" / f"{relation['cible']}.py"
        if (
            not relation["nullable"] and relation["cible"] != "utilisateur" and cles_appliquees
            and routeur_parent.is_file()
            and "IntegrityError" in routeur_parent.read_text(encoding="utf-8")
        ):
            restreinte = relation
            break
    ctx["relation_restreinte"] = restreinte
    ctx["utilisateur_cible"] = any(r["cible"] == "utilisateur" for r in ctx["relations"])
    plan.creations.append(_fichier_test(ctx))


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
    ctx = construire_contexte(nom, champs, pluriel, defaut, racine)
    plan = Plan()

    if type_generation == "config" and ctx["relations"]:
        raise ErreurPlan("Les relations (fk) n'ont pas de sens pour une configuration.")

    if protege:
        if not (racine / "app/dependances.py").exists():
            raise ErreurPlan("--protege demande l'authentification : lance d'abord « alioune auth ».")
        ctx["protege"] = True

    snake = ctx["nom_snake"]

    if type_generation == "ressource":
        plan.creations += [
            _fichier_modele(ctx), _fichier_schema(ctx), _fichier_service(ctx),
            _fichier_routeur(ctx), _fichier_migration(racine, ctx),
        ]
        _inscrire_modele(plan, ctx)
        _inscrire_routeur(plan, ctx)
        _verifier_relations(racine, plan, ctx)
        _preparer_tests(racine, plan, ctx)

    elif type_generation == "modele":
        plan.creations.append(_fichier_modele(ctx))
        _inscrire_modele(plan, ctx)
        _verifier_relations(racine, plan, ctx)

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
