# Journal des modifications

## 0.4.1

- Nouvelle page d'accueil des projets créés : statut animé, liste des ressources de l'API (avec liens vers la documentation), commandes utiles, thème clair/sombre automatique.
- La page distingue la version de l'application (`version` dans `app/config.py`, « v0.1.0 » par défaut) de la version d'alioune qui a généré le projet (affichée en pied de page).

## 0.4.0

- Listes générées : recherche `?q=` (champs texte, insensible à la casse), tri `?tri=nom` / `?tri=-nom` et filtres sur les champs `bool` et les relations `fk`.
- Chaque ressource générée est livrée avec des tests de tri, de recherche et de filtre.

## 0.3.0

- `alioune generate` : relations plusieurs-à-plusieurs avec `m2m(modele)` (table d'association, migration, champ `*_ids` dans l'API, vérification 422).
- `alioune generate` : auto-référence (`parent:fk(categorie)?` dans `categorie`) pour les hiérarchies.
- Fichiers Python générés : lignes vides et tuples normalisés.

## 0.2.0

- `alioune generate` : relations entre tables avec le type `fk` (`categorie:fk`, `origine:fk(pays)?`) : clé étrangère, index, relation SQLAlchemy, migration, vérification de l'existence (422) et refus de suppression d'un élément utilisé (409).
- Les ressources générées refusent `null` sur un champ obligatoire lors d'une modification (422 au lieu d'une erreur serveur).
- Chaque ressource générée expose `donnees_valides()` dans ses tests, que les ressources liées réutilisent.
- Les projets créés activent les clés étrangères de SQLite (dans l'application et dans les tests).
- Nouveau README illustré (démo animée, captures et schémas).

## 0.1.1

- Ajout des liens du projet (GitHub) sur la page PyPI.

## 0.1.0

- `alioune new` : crée un projet FastAPI fonctionnel (SQLAlchemy 2.0, Alembic, tests, page d'accueil).
- `alioune generate` : ressource, modèle, schéma, service, routeur, migration, config.
- `alioune auth` : authentification optionnelle (JWT, Argon2, rôles).
- `alioune serve`, `migrate`, `routes`, `info`.
