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


# --- Relations (fk) ---------------------------------------------------------

def test_analyse_des_relations() -> None:
    champs = analyser_champs("categorie:fk,origine:fk(pays)?,fournisseur_id:fk")

    assert [c.nom for c in champs] == ["categorie_id", "origine_id", "fournisseur_id"]
    assert [c.cible for c in champs] == ["categorie", "pays", "fournisseur"]
    assert champs[1].nullable and champs[1].ondelete == "SET NULL"
    assert champs[0].ondelete == "RESTRICT"
    assert champs[0].annotation == "int" and champs[1].annotation == "int | None"
    assert champs[0].relation == "categorie"


@pytest.mark.parametrize("texte", ["x:fk?(pays)", "categorie:fk,categorie:str", "x:fk(Pays Bas)"])
def test_relations_invalides(texte: str) -> None:
    with pytest.raises(ErreurPlan):
        analyser_champs(texte)


def _ressource(nom: str, champs: str, *options: str):
    return runner.invoke(app, ["g", "ressource", nom, "-c", champs, *options])


def test_ressource_avec_relation(projet: Path) -> None:
    assert _ressource("categorie", "nom:str").exit_code == 0
    resultat = _ressource("produit", "nom:str,categorie:fk,fournisseur:fk(categorie)?")

    assert resultat.exit_code == 0, resultat.output
    modele = (projet / "app/modeles/produit.py").read_text()
    assert 'ForeignKey("categories.id", ondelete="RESTRICT")' in modele
    assert 'ForeignKey("categories.id", ondelete="SET NULL")' in modele
    assert 'categorie: Mapped["Categorie"] = relationship(foreign_keys=[categorie_id])' in modele
    assert 'fournisseur: Mapped["Categorie | None"]' in modele
    migration = next((projet / "alembic/versions").glob("*produits.py")).read_text()
    assert 'sa.ForeignKeyConstraint(["categorie_id"], ["categories.id"], ondelete="RESTRICT")' in migration
    assert 'op.create_index(op.f("ix_produits_categorie_id")' in migration
    routeur = (projet / "app/routeurs/produit.py").read_text()
    assert "_verifier_relations" in routeur and "from app.modeles.categorie import Categorie" in routeur
    assert "def donnees_valides" in (projet / "tests/test_produits.py").read_text()
    _compiler_tout(projet)


def test_relation_vers_un_modele_absent_avertit(projet: Path) -> None:
    resultat = _ressource("produit", "nom:str,categorie:fk")

    assert resultat.exit_code == 0
    assert "n'existe pas encore" in resultat.output
    assert "Tests non générés" in resultat.output
    assert not (projet / "tests/test_produits.py").exists()


def test_relation_respecte_le_pluriel_du_modele_lie(projet: Path) -> None:
    runner.invoke(app, ["g", "ressource", "ville", "-c", "nom:str", "--pluriel", "villes_senegal"])
    _ressource("quartier", "nom:str,ville:fk")

    assert 'ForeignKey("villes_senegal.id"' in (projet / "app/modeles/quartier.py").read_text()


def test_auto_reference_obligatoire_refusee_et_config_refusee(projet: Path) -> None:
    assert _ressource("categorie", "nom:str,parent:fk(categorie)").exit_code == 1
    resultat = runner.invoke(app, ["g", "config", "stripe", "-c", "cle:fk"])
    assert resultat.exit_code == 1


def test_relation_vers_utilisateur(projet: Path) -> None:
    assert runner.invoke(app, ["auth", "--sans-installation"]).exit_code == 0

    resultat = _ressource("commande", "reference:str,client:fk(utilisateur)")

    assert resultat.exit_code == 0, resultat.output
    assert 'ForeignKey("utilisateurs.id"' in (projet / "app/modeles/commande.py").read_text()
    test = (projet / "tests/test_commandes.py").read_text()
    assert "_creer_utilisateur" in test and "import uuid" in test
    assert "409" not in test  # pas de route de suppression sur les utilisateurs
    _compiler_tout(projet)


# --- Auto-référence et plusieurs-à-plusieurs (m2m) ---------------------------

def test_analyse_m2m() -> None:
    champs = analyser_champs("nom:str,etiquettes:m2m(etiquette)")

    m2m = [c for c in champs if c.est_m2m]
    assert len(m2m) == 1 and m2m[0].cible == "etiquette"
    assert m2m[0].ids == "etiquettes_ids"


@pytest.mark.parametrize("texte", ["x:m2m", "x:m2m(etiquette)?", "x:m2m(Eti quette)"])
def test_m2m_invalides(texte: str) -> None:
    with pytest.raises(ErreurPlan):
        analyser_champs(texte)


def test_m2m_vers_soi_meme_refuse(projet: Path) -> None:
    resultat = _ressource("etiquette", "nom:str,voisines:m2m(etiquette)")

    assert resultat.exit_code == 1


def test_ressource_avec_m2m(projet: Path) -> None:
    assert _ressource("etiquette", "nom:str").exit_code == 0
    resultat = _ressource("produit", "nom:str,etiquettes:m2m(etiquette)")

    assert resultat.exit_code == 0, resultat.output
    modele = (projet / "app/modeles/produit.py").read_text()
    assert "produits_etiquettes = Table(" in modele
    assert "relationship(secondary=produits_etiquettes)" in modele
    assert "def etiquettes_ids" in modele
    assert "etiquettes_ids" in (projet / "app/schemas/produit.py").read_text()
    migration = next((projet / "alembic/versions").glob("*produits.py")).read_text()
    assert '"produits_etiquettes"' in migration and "ondelete=\"CASCADE\"" in migration
    assert "etiquettes" not in migration.split("create_table(")[1].split("sa.PrimaryKeyConstraint")[0]
    _compiler_tout(projet)


def test_m2m_sans_champ_simple_refuse(projet: Path) -> None:
    _ressource("etiquette", "nom:str")

    assert _ressource("produit", "etiquettes:m2m(etiquette)").exit_code == 1


def test_ressource_auto_referencee(projet: Path) -> None:
    resultat = _ressource("categorie", "nom:str,parent:fk(categorie)?")

    assert resultat.exit_code == 0, resultat.output
    modele = (projet / "app/modeles/categorie.py").read_text()
    assert "remote_side=[id]" in modele
    assert 'ForeignKey("categories.id", ondelete="SET NULL")' in modele
    assert "test_associer_parent" in (projet / "tests/test_categories.py").read_text()
    _compiler_tout(projet)


# --- Recherche, tri et filtres dans les listes -------------------------------

def test_liste_avec_recherche_tri_et_filtres(projet: Path) -> None:
    _ressource("categorie", "nom:str")
    resultat = _ressource("produit", "nom:str,note:text?,actif:bool,categorie:fk")

    assert resultat.exit_code == 0, resultat.output
    routeur = (projet / "app/routeurs/produit.py").read_text()
    assert "Recherche dans : nom, note" in routeur
    assert 'pattern=r"^-?(id|nom|note|actif|categorie_id|cree_le|modifie_le)$"' in routeur
    assert "actif: bool | None = None" in routeur and "categorie_id: int | None = None" in routeur
    service = (projet / "app/services/produit.py").read_text()
    assert "ilike(motif" in service and "filtres" in service
    tests = (projet / "tests/test_produits.py").read_text()
    for nom in ("test_trier_les_produits", "test_rechercher_des_produits", "test_filtrer_les_produits"):
        assert nom in tests
    _compiler_tout(projet)


def test_liste_sans_champ_texte_ni_filtre(projet: Path) -> None:
    resultat = _ressource("mesure", "valeur:int")

    assert resultat.exit_code == 0, resultat.output
    routeur = (projet / "app/routeurs/mesure.py").read_text()
    assert "    q: Annotated" not in routeur and "filtres = {" not in routeur and "    tri: Annotated" in routeur
    tests = (projet / "tests/test_mesures.py").read_text()
    assert "test_rechercher" not in tests and "test_filtrer" not in tests
    _compiler_tout(projet)
