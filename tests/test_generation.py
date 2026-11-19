"""Tests de `alioune generate` et `alioune auth` sur un projet généré (sans installer de dépendances)."""

import py_compile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alioune.cli import app
from alioune.generateurs import analyser_champs
from alioune.migrations import tete_actuelle
from alioune.noms import en_pascal_case, pluriel_francais
from alioune.plan import ErreurPlan

runner = CliRunner()


@pytest.fixture()
def projet(tmp_path, monkeypatch) -> Path:
    monkeypatch.chdir(tmp_path)
    resultat = runner.invoke(app, ["new", "demo", "--base", "sqlite", "--sans-installation", "--sans-git"])
    assert resultat.exit_code == 0, resultat.output
    monkeypatch.chdir(tmp_path / "demo")
    return tmp_path / "demo"


def _compiler_tout(racine: Path) -> None:
    for fichier in racine.rglob("*.py"):
        if ".venv" not in fichier.parts:
            py_compile.compile(str(fichier), doraise=True)


def test_pluriels_et_casse() -> None:
    assert pluriel_francais("produit") == "produits"
    assert pluriel_francais("ligne_commande") == "lignes_commande"
    assert pluriel_francais("animal") == "animaux"
    assert pluriel_francais("bateau") == "bateaux"
    assert pluriel_francais("pays") == "pays"
    assert en_pascal_case("ligne-commande") == "LigneCommande"


def test_analyse_des_champs() -> None:
    champs = analyser_champs("nom:str,prix:decimal,note:text?")
    assert [c.nom for c in champs] == ["nom", "prix", "note"]
    assert champs[2].nullable and champs[2].annotation == "str | None"


@pytest.mark.parametrize("texte", ["id:int", "nom:inconnu", "nom,nom", "9x:str"])
def test_champs_invalides(texte: str) -> None:
    with pytest.raises(ErreurPlan):
        analyser_champs(texte)


def test_ressource_cree_les_fichiers_et_les_inscrit(projet: Path) -> None:
    resultat = runner.invoke(app, ["g", "ressource", "produit", "-c", "nom:str,prix:decimal"])

    assert resultat.exit_code == 0, resultat.output
    for fichier in ["app/modeles/produit.py", "app/schemas/produit.py", "app/services/produit.py",
                    "app/routeurs/produit.py", "tests/test_produits.py"]:
        assert (projet / fichier).is_file(), fichier
    assert "import Produit" in (projet / "app/modeles/__init__.py").read_text()
    routeurs = (projet / "app/routeurs/__init__.py").read_text()
    assert "routeur_api.include_router(routeur_produit)" in routeurs
    assert len(list((projet / "alembic/versions").glob("*creer_table_produits.py"))) == 1
    _compiler_tout(projet)


def test_les_migrations_sont_chainees(projet: Path) -> None:
    runner.invoke(app, ["g", "ressource", "produit"])
    premiere = tete_actuelle(projet)
    runner.invoke(app, ["g", "ressource", "client"])
    deuxieme = tete_actuelle(projet)

    assert premiere and deuxieme and premiere != deuxieme
    fichier = next((projet / "alembic/versions").glob("*clients.py"))
    assert f'"{premiere}"' in fichier.read_text()


def test_generate_est_idempotent_sur_les_inscriptions(projet: Path) -> None:
    runner.invoke(app, ["g", "modele", "produit"])
    runner.invoke(app, ["g", "modele", "produit", "--force"])

    assert (projet / "app/modeles/__init__.py").read_text().count("import Produit") == 1


def test_conflit_sans_force_ne_modifie_rien(projet: Path) -> None:
    runner.invoke(app, ["g", "modele", "produit"])
    avant = (projet / "app/modeles/produit.py").read_text()

    resultat = runner.invoke(app, ["g", "ressource", "produit", "-c", "autre:int"])

    assert resultat.exit_code == 1
    assert (projet / "app/modeles/produit.py").read_text() == avant
    assert not (projet / "app/schemas/produit.py").exists()


def test_simuler_n_ecrit_rien(projet: Path) -> None:
    resultat = runner.invoke(app, ["g", "ressource", "produit", "--simuler"])

    assert resultat.exit_code == 0
    assert not (projet / "app/modeles/produit.py").exists()
    assert not list((projet / "alembic/versions").glob("*.py"))


def test_migration_vide_et_config(projet: Path) -> None:
    assert runner.invoke(app, ["g", "migration", "ajouter_index"]).exit_code == 0
    assert len(list((projet / "alembic/versions").glob("*ajouter_index.py"))) == 1

    assert runner.invoke(app, ["g", "config", "cloudinary", "-c", "nom_cloud:str,cle_api:str"]).exit_code == 0
    assert "CLOUDINARY_CLE_API=" in (projet / ".env.example").read_text()
    _compiler_tout(projet)


def test_protege_exige_auth(projet: Path) -> None:
    resultat = runner.invoke(app, ["g", "ressource", "client", "--protege"])

    assert resultat.exit_code == 1
    assert not (projet / "app/modeles/client.py").exists()


def test_auth_puis_ressource_protegee(projet: Path) -> None:
    resultat = runner.invoke(app, ["auth", "--sans-installation"])
    assert resultat.exit_code == 0, resultat.output
    assert (projet / "app/dependances.py").is_file()
    assert "pyjwt" in (projet / "requirements.txt").read_text()

    assert runner.invoke(app, ["g", "ressource", "client", "--protege"]).exit_code == 0
    routeur = (projet / "app/routeurs/client.py").read_text()
    assert "dependencies=[Depends(utilisateur_courant)]" in routeur
    _compiler_tout(projet)

    # Relancer auth ne doit ni dupliquer les dépendances ni les inscriptions.
    assert runner.invoke(app, ["auth", "--sans-installation", "--force"]).exit_code == 0
    assert (projet / "requirements.txt").read_text().lower().count("pyjwt") == 1
    assert (projet / "app/routeurs/__init__.py").read_text().count("routeur_auth") == 2


def test_hors_projet_les_commandes_echouent(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["g", "modele", "produit"]).exit_code == 1
    assert runner.invoke(app, ["auth"]).exit_code == 1
