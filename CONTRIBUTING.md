# Contribuer à alioune

```bash
git clone <url-du-depot>
cd alioune-cli
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

## Où est quoi

| Dossier / fichier | Rôle |
|---|---|
| `src/alioune/cli.py` | Les commandes (`new`, `generate`, `auth`, `serve`...) |
| `src/alioune/gabarits/projet/` | Ce que `alioune new` crée |
| `src/alioune/gabarits/generer/` | Les gabarits de `alioune generate` |
| `src/alioune/gabarits/auth/` | Ce que `alioune auth` installe |
| `src/alioune/generateurs.py` | Logique de `generate` (champs, plan d'écriture) |
| `tests/` | Tests du CLI |

## Règles des gabarits

- Un fichier `.j2` est rendu avec Jinja2 ; les autres sont copiés tels quels.
- `dot_xxx` devient `.xxx` (fichiers cachés).
- Le code généré est écrit en français, avec les API à jour de FastAPI et SQLAlchemy 2.0.
- Tout changement de gabarit doit garder le projet généré fonctionnel : lance `pytest`, puis génère un vrai projet et exécute ses tests.

## Proposer un changement

1. Crée une branche, modifie, ajoute un test.
2. Vérifie `pytest`, puis ouvre une Pull Request.
