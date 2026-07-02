import click
from ckanext.fair3r.tasks import update_fdf_schema


def get_commands():
    return [fair3r]


@click.group()
def fair3r():
    """Handle Fair3R commands."""
    pass


@fair3r.command(name="update-schema")
def update_schema():
    """Doawnload and update FDF schema from github repository."""
    result = update_fdf_schema()
    if result["success"]:
        click.secho(result["message"], fg="green")
    else:
        click.secho(result["message"], fg="red")
        raise click.Abort()
