"""Tests du CLI : génération d'un projet sans installation de dépendances."""

import json

from typer.testing import CliRunner

from alioune.cli import app
from alioune.moteur import traduire_nom
from alioune.noms import en_snake_case, nom_affichage, nom_projet_valide

runner = CliRunner()


def test_traduire_nom() -> None:
    assert traduire_nom("dot_env.example.j2") == ".env.example"
    assert traduire_nom("config.py.j2") == "config.py"
    assert traduire_nom("main.py") == "main.py"


def test_noms() -> None:
    assert en_snake_case("Ma Boutique-en.ligne") == "ma_boutique_en_ligne"
    assert nom_affichage("ma-boutique_en.ligne") == "Ma Boutique En Ligne"
    assert nom_projet_valide("sen-solution")
    assert not nom_projet_valide("../evil")
    assert not nom_projet_valide("avec espace")


def test_new_cree_un_projet_complet(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    resultat = runner.invoke(app, ["new", "ma-boutique", "--sans-installation", "--sans-git"])

    assert resultat.exit_code == 0, resultat.output
    racine = tmp_path / "ma-boutique"
    for attendu in [
        ".env", ".env.example", ".gitignore", "alioune.json", "alembic.ini",
        "alembic/env.py", "alembic/versions/.gitkeep", "app/main.py", "app/config.py",
        "app/modeles/base.py", "app/routeurs/accueil.py", "app/gabarits/accueil.html",
        "tests/test_sante.py", "requirements.txt",
    ]:
        assert (racine / attendu).exists(), attendu

    assert json.loads((racine / "alioune.json").read_text())["nom"] == "ma-boutique"
    assert "changez-moi" not in (racine / ".env").read_text()
    assert "changez-moi" in (racine / ".env.example").read_text()
    assert "psycopg" in (racine / "requirements.txt").read_text()


def test_new_sqlite_n_ajoute_pas_psycopg(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    resultat = runner.invoke(app, ["new", "demo", "--base", "sqlite", "--sans-installation", "--sans-git"])

    assert resultat.exit_code == 0, resultat.output
    assert "psycopg" not in (tmp_path / "demo" / "requirements.txt").read_text()
    assert "sqlite:///./demo.db" in (tmp_path / "demo" / ".env").read_text()


def test_new_refuse_un_dossier_non_vide(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "existant").mkdir()
    (tmp_path / "existant" / "fichier.txt").write_text("x")

    resultat = runner.invoke(app, ["new", "existant", "--sans-installation", "--sans-git"])

    assert resultat.exit_code == 1


def test_new_refuse_un_nom_invalide(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    resultat = runner.invoke(app, ["new", "../evil", "--sans-installation"])

    assert resultat.exit_code == 1
