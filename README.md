# alioune

Générateur de projets et de code pour **FastAPI** : l'équivalent d'Angular CLI (`ng new`) ou d'Artisan (Laravel), pensé pour une architecture en couches et du code en français.

```bash
pipx install alioune          # ou : pip install alioune
alioune new ma-boutique
cd ma-boutique
alioune serve                 # http://127.0.0.1:8000
```

`alioune new` crée un projet **fonctionnel dès le premier lancement** : environnement virtuel, dépendances installées, `.env`, SQLAlchemy 2.0, Alembic, tests, et une page d'accueil avec le nom du projet et les liens vers les documentations.

## Générer du code (comme `ng g` / `php artisan make:`)

```bash
alioune g ressource produit -c "nom:str,prix:decimal,description:text?,actif:bool"
alioune migrate
```

Une **ressource** crée d'un coup : modèle, schémas (création / mise à jour / lecture), service (CRUD), routeur (liste paginée, lecture, création, PATCH, suppression), migration Alembic chaînée et un fichier de tests. Le modèle et le routeur sont inscrits automatiquement dans `app/modeles/__init__.py` et `app/routeurs/__init__.py`.

| Type | Génère |
|---|---|
| `ressource` | tout ce qui précède |
| `modele`, `schema`, `service`, `routeur` | un seul fichier (avec inscription si besoin) |
| `migration` | une migration vide, chaînée à la dernière |
| `config` | une classe de paramètres (`pydantic-settings`) + variables dans `.env` |

Options : `-c/--champs` (types : `str text int float decimal bool date datetime`, `?` = facultatif), `--pluriel`, `--protege`, `--simuler` (n'écrit rien), `--force`. Un fichier existant n'est jamais écrasé sans `--force`.

## Authentification (comme Breeze pour Laravel)

L'authentification est **optionnelle** : si tu as la tienne, ne lance rien.

```bash
alioune auth
alioune migrate
python -m app.creer_admin admin@exemple.com
alioune g ressource commande --protege      # route réservée aux utilisateurs connectés
```

Installe : modèle `Utilisateur`, hachage Argon2, JWT, routes `POST /api/auth/inscription`, `POST /api/auth/connexion`, `GET /api/auth/moi`, dépendances `UtilisateurCourant` / `UtilisateurAdmin` / `exiger_role(...)`, migration et tests. Le code installé t'appartient : modifie-le librement.

## Commandes

| Commande | Rôle |
|---|---|
| `alioune generate` (`g`) `<type> <nom>` | Génère du code (voir ci-dessus) |
| `alioune auth` | Installe l'authentification |
| `alioune new <nom> [--base postgresql\|sqlite] [--sans-installation] [--sans-git]` | Crée un projet |
| `alioune serve [--port 8000]` | Lance uvicorn avec rechargement automatique |
| `alioune migrate [--annuler]` | Applique (ou annule) les migrations Alembic |
| `alioune routes` | Liste les routes de l'application |
| `alioune info` | Affiche les informations du projet |

## Développement

```bash
pip install -e ".[dev]"
pytest
```

Les gabarits sont dans `src/alioune/gabarits/`. Un fichier `.j2` est rendu avec Jinja2, les autres sont copiés tels quels, et `dot_` devient `.` pour les fichiers cachés.

## Licence

MIT
