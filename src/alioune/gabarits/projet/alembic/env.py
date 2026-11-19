from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import obtenir_parametres
from app.modeles import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# L'URL vient de .env : on échappe les % pour le parseur de configuration d'Alembic.
config.set_main_option(
    "sqlalchemy.url", obtenir_parametres().url_base_de_donnees.replace("%", "%%")
)

cible_metadata = Base.metadata


def executer_migrations_hors_ligne() -> None:
    """Génère le SQL sans se connecter à la base."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=cible_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def executer_migrations_en_ligne() -> None:
    """Applique les migrations sur la base."""
    moteur = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with moteur.connect() as connexion:
        context.configure(
            connection=connexion,
            target_metadata=cible_metadata,
            compare_type=True,
            render_as_batch=connexion.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    executer_migrations_hors_ligne()
else:
    executer_migrations_en_ligne()
