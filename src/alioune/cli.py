"""Point d'entrée de la commande `alioune`."""

from __future__ import annotations

import subprocess
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from alioune import __version__
from alioune.auth import preparer_auth
from alioune.generateurs import preparer_generation
from alioune.nouveau import ErreurCreation, creer_projet
from alioune.noms import nom_projet_valide
from alioune.plan import ErreurPlan, Rapport, appliquer
from alioune.projet import lire_configuration, python_a_utiliser, trouver_racine

app = typer.Typer(
    name="alioune",
    help="Générateur de projets et de code pour FastAPI.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


class TypeBase(str, Enum):
    postgresql = "postgresql"
    sqlite = "sqlite"


def _afficher_version(valeur: bool) -> None:
    if valeur:
        console.print(f"alioune {__version__}")
        raise typer.Exit()


@app.callback()
def principal(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-v", callback=_afficher_version, is_eager=True,
                     help="Affiche la version et quitte."),
    ] = None,
) -> None:
    pass


def _racine_ou_quitter() -> Path:
    racine = trouver_racine()
    if racine is None:
        console.print(
            "[red]Aucun projet alioune ici.[/red] "
            "Place-toi dans un projet créé avec [bold]alioune new[/bold]."
        )
        raise typer.Exit(code=1)
    return racine


@app.command("new")
def nouveau(
    nom: Annotated[str, typer.Argument(help="Nom du projet (devient le nom du dossier).")],
    base: Annotated[
        TypeBase, typer.Option("--base", help="Base de données du projet.")
    ] = TypeBase.postgresql,
    sans_installation: Annotated[
        bool, typer.Option("--sans-installation", help="Ne crée pas le .venv et n'installe rien.")
    ] = False,
    sans_git: Annotated[
        bool, typer.Option("--sans-git", help="N'initialise pas de dépôt Git.")
    ] = False,
) -> None:
    """Crée un projet FastAPI complet, prêt à être lancé avec uvicorn."""
    if not nom_projet_valide(nom):
        console.print(
            f"[red]Nom invalide :[/red] « {nom} ». "
            "Utilise des lettres, chiffres, tirets, underscores ou points."
        )
        raise typer.Exit(code=1)

    try:
        with console.status("[bold]Création du projet..." if sans_installation
                            else "[bold]Création du projet et installation des dépendances..."):
            resultat = creer_projet(
                nom=nom,
                base=base.value,
                installer=not sans_installation,
                initialiser_git=not sans_git,
                dossier_parent=Path.cwd(),
            )
    except ErreurCreation as erreur:
        console.print(f"[red]{erreur}[/red]")
        raise typer.Exit(code=1)

    for fichier in sorted(resultat.fichiers):
        console.print(f"  [green]CREATE[/green] {nom}/{fichier.as_posix()}")
    if resultat.git_initialise:
        console.print("  [green]git[/green]    dépôt initialisé")
    console.print(f"\n[bold green]Projet « {nom} » créé.[/bold green]\n")

    console.print("Pour démarrer :")
    console.print(f"  cd {nom}")
    if resultat.venv_cree:
        console.print("  alioune serve            [dim]# ou : uvicorn app.main:app --reload[/dim]")
    else:
        console.print("  python -m venv .venv && source .venv/bin/activate")
        console.print("  pip install -r requirements-dev.txt")
        console.print("  uvicorn app.main:app --reload")
    console.print("\nPuis ouvre [bold]http://127.0.0.1:8000[/bold]")


class TypeGeneration(str, Enum):
    ressource = "ressource"
    modele = "modele"
    schema = "schema"
    service = "service"
    routeur = "routeur"
    migration = "migration"
    config = "config"


def _afficher_rapport(rapport: Rapport, simuler: bool) -> None:
    prefixe = "[dim](simulation)[/dim] " if simuler else ""
    for chemin in rapport.crees:
        console.print(f"  {prefixe}[green]CREATE[/green] {chemin.as_posix()}")
    for chemin in rapport.modifies:
        console.print(f"  {prefixe}[cyan]UPDATE[/cyan] {chemin.as_posix()}")
    for message in rapport.avertissements:
        console.print(f"  [yellow]ATTENTION[/yellow] {message}")


@app.command("generate")
@app.command("g", hidden=True)
def generer(
    type_generation: Annotated[
        TypeGeneration, typer.Argument(help="Ce qu'il faut générer.", metavar="TYPE")
    ],
    nom: Annotated[str, typer.Argument(help="Nom au singulier (produit, ligne_commande...).")],
    champs: Annotated[
        Optional[str],
        typer.Option(
            "--champs", "-c",
            help="Champs : nom:str,prix:decimal,note:text? (types : str text int float decimal bool date datetime ; ? = facultatif).",
        ),
    ] = None,
    pluriel: Annotated[
        Optional[str], typer.Option("--pluriel", help="Pluriel si la règle automatique se trompe.")
    ] = None,
    protege: Annotated[
        bool, typer.Option("--protege", help="Exige un utilisateur connecté (après alioune auth).")
    ] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Remplace les fichiers existants.")] = False,
    simuler: Annotated[bool, typer.Option("--simuler", help="Affiche ce qui serait fait, sans écrire.")] = False,
) -> None:
    """Génère du code prêt à l'emploi : ressource, modele, schema, service, routeur, migration, config."""
    racine = _racine_ou_quitter()
    try:
        plan = preparer_generation(
            racine, type_generation.value, nom, champs=champs, pluriel=pluriel, protege=protege
        )
        rapport = appliquer(plan, racine, ecraser=force, simuler=simuler)
    except ErreurPlan as erreur:
        console.print(f"[red]{erreur}[/red]")
        raise typer.Exit(code=1)
    _afficher_rapport(rapport, simuler)
    if type_generation in (TypeGeneration.ressource, TypeGeneration.migration) and not simuler:
        console.print("\nPuis : [bold]alioune migrate[/bold]")


@app.command("auth")
def installer_auth(
    force: Annotated[bool, typer.Option("--force", "-f", help="Remplace les fichiers existants.")] = False,
    sans_installation: Annotated[
        bool, typer.Option("--sans-installation", help="N'installe pas les nouvelles dépendances.")
    ] = False,
    simuler: Annotated[bool, typer.Option("--simuler", help="Affiche ce qui serait fait, sans écrire.")] = False,
) -> None:
    """Installe l'authentification (inscription, connexion JWT, rôles) dans le projet."""
    racine = _racine_ou_quitter()
    try:
        rapport = appliquer(preparer_auth(racine), racine, ecraser=force, simuler=simuler)
    except ErreurPlan as erreur:
        console.print(f"[red]{erreur}[/red]")
        raise typer.Exit(code=1)
    _afficher_rapport(rapport, simuler)
    if simuler:
        return

    python, venv_trouve = python_a_utiliser(racine)
    if not sans_installation and venv_trouve:
        with console.status("[bold]Installation des dépendances..."):
            resultat = subprocess.run(
                [python, "-m", "pip", "install", "--disable-pip-version-check", "-q",
                 "-r", "requirements.txt"],
                cwd=racine, capture_output=True, text=True,
            )
        if resultat.returncode != 0:
            console.print(f"[red]Échec de pip :[/red]\n{resultat.stderr.strip()[-800:]}")
            raise typer.Exit(code=1)
    elif not venv_trouve:
        console.print("[yellow].venv introuvable : lance pip install -r requirements.txt toi-même.[/yellow]")

    console.print("\n[bold green]Authentification installée.[/bold green]")
    console.print("  1. [bold]alioune migrate[/bold]                      crée la table des utilisateurs")
    console.print("  2. [bold]python -m app.creer_admin admin@exemple.com[/bold]   crée un administrateur")
    console.print("  3. Routes : POST /api/auth/inscription, POST /api/auth/connexion, GET /api/auth/moi")
    console.print("  4. Protéger une ressource : [bold]alioune g ressource produit --protege[/bold]")


@app.command("serve")
def servir(
    hote: Annotated[str, typer.Option("--hote", help="Adresse d'écoute.")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", "-p", help="Port d'écoute.")] = 8000,
    sans_rechargement: Annotated[
        bool, typer.Option("--sans-rechargement", help="Désactive le rechargement automatique.")
    ] = False,
) -> None:
    """Lance le serveur de développement (uvicorn) du projet."""
    racine = _racine_ou_quitter()
    python, venv_trouve = python_a_utiliser(racine)
    if not venv_trouve:
        console.print("[yellow].venv introuvable : utilisation de l'interpréteur courant.[/yellow]")

    commande = [python, "-m", "uvicorn", "app.main:app", "--host", hote, "--port", str(port)]
    if not sans_rechargement:
        commande.append("--reload")
    try:
        subprocess.run(commande, cwd=racine)
    except KeyboardInterrupt:
        pass


@app.command("migrate")
def migrer(
    annuler: Annotated[
        bool, typer.Option("--annuler", help="Annule la dernière migration au lieu d'appliquer.")
    ] = False,
) -> None:
    """Applique les migrations Alembic (ou annule la dernière avec --annuler)."""
    racine = _racine_ou_quitter()
    python, _ = python_a_utiliser(racine)
    arguments = ["downgrade", "-1"] if annuler else ["upgrade", "head"]
    code = subprocess.run([python, "-m", "alembic", *arguments], cwd=racine).returncode
    raise typer.Exit(code=code)


# On s'appuie sur le schéma OpenAPI (API publique de FastAPI) plutôt que sur
# `app.routes`, dont la structure interne change selon les versions.
_SCRIPT_ROUTES = """
from app.main import app
for chemin, operations in app.openapi()["paths"].items():
    for methode, details in operations.items():
        print(f"{methode.upper()}\\t{chemin}\\t{details.get('summary', '')}")
"""


@app.command("routes")
def lister_routes() -> None:
    """Liste les routes documentées (OpenAPI) de l'application."""
    racine = _racine_ou_quitter()
    python, _ = python_a_utiliser(racine)
    resultat = subprocess.run([python, "-c", _SCRIPT_ROUTES], cwd=racine, capture_output=True, text=True)
    if resultat.returncode != 0:
        console.print(f"[red]{resultat.stderr.strip()}[/red]")
        raise typer.Exit(code=1)

    tableau = Table(show_header=True, header_style="bold")
    tableau.add_column("Méthodes")
    tableau.add_column("Chemin")
    tableau.add_column("Résumé")
    for ligne in resultat.stdout.strip().splitlines():
        methodes, chemin, resume = ligne.split("\t")
        tableau.add_row(methodes, chemin, resume)
    console.print(tableau)


@app.command("info")
def informations() -> None:
    """Affiche les informations du projet courant."""
    racine = _racine_ou_quitter()
    configuration = lire_configuration(racine)
    console.print(f"[bold]{configuration['nom']}[/bold]  ({racine})")
    console.print(f"  base de données : {configuration['base']}")
    console.print(f"  généré avec alioune {configuration['version_alioune']}")
