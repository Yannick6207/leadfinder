import click
from .extensions import db
from .services.seed import seed_database


def register_commands(app):
    @app.cli.command("init-db")
    def init_db():
        db.create_all(); click.echo("Database aangemaakt.")

    @app.cli.command("seed")
    @click.option("--reset", is_flag=True)
    def seed(reset):
        click.echo(f"{seed_database(reset=reset)} fictieve leads beschikbaar.")
