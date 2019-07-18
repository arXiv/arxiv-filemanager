"""Generate auth token."""
import click

from pytz import UTC
import uuid
from datetime import timedelta, datetime
from arxiv.users import auth, domain
from filemanager.factory import create_web_app

app = create_web_app()
app.app_context().push()


@app.cli.command()
@click.option('--user_id', prompt='Numeric user ID')
@click.option('--email', prompt='Email address')
@click.option('--username', prompt='Username')
@click.option('--first_name', prompt='First name', default='Jane')
@click.option('--last_name', prompt='Last name', default='Doe')
@click.option('--suffix_name', prompt='Name suffix', default='IV')
@click.option('--affiliation', prompt='Affiliation',
              default='Cornell University')
@click.option('--rank', prompt='Numeric rank', default=3)
@click.option('--country', prompt='Alpha-2 country code', default='us')
@click.option('--default_category', prompt='Default category',
              default='astro-ph.GA')
@click.option('--submission_groups', prompt='Submission groups (comma delim)',
              default='grp_physics')
@click.option('--endorsements', prompt='Endorsement categories (comma delim)',
              default='astro-ph.CO,astro-ph.GA')
@click.option('--scope', prompt='Authorization scope (comma delim)',
              default='upload:read,upload:write,upload:admin')
def generate_token(user_id: str, email: str, username: str,
                   first_name: str = 'Jane', last_name: str = 'Doe',
                   suffix_name: str = 'IV',
                   affiliation: str = 'Cornell University',
                   rank: int = 3,
                   country: str = 'us',
                   default_category: str = 'astro-ph.GA',
                   submission_groups: str = 'grp_physics',
                   endorsements: str = 'astro-ph.CO,astro-ph.GA',
                   scope: str = 'upload:read,upload:write,upload:admin') \
        -> None:
    """
    Generate a custom auth token given parameters.

    Parameters
    ----------
    user_id : str
        User id
    email : str
        E-mail address
    username : str
        Username of token owner
    first_name : str
        First name
    last_name : str
        Last name
    suffix_name : str
        Suffix for name
    affiliation : str
        Affiliation of toekn owner
    rank : str
        Some kind of rank
    country : str
        Country of token owner
    default_category : str
        Default category for user
    submission_groups: str
        Submission groups token owner belongs to.
    endorsements : str
        Comma separated list of groups token owner is endorsed for
    scope : str
        Comma separated list of scope permissions for this token owner.

    """
    # Specify the validity period for the session.
    start = datetime.now(tz=UTC)
    end = start + timedelta(seconds=36000)   # Make this as long as you want.

    # Create a user with endorsements in astro-ph.CO and .GA.
    session = domain.Session(
        session_id=str(uuid.uuid4()),
        start_time=start, end_time=end,
        user=domain.User(
            user_id=user_id,
            email=email,
            username=username,
            name=domain.UserFullName(first_name, last_name, suffix_name),
            profile=domain.UserProfile(
                affiliation=affiliation,
                rank=int(rank),
                country=country,
                default_category=domain.Category(default_category),
                submission_groups=submission_groups.split(',')
            )
        ),
        authorizations=domain.Authorizations(
            scopes=[scope.split(',')],
            endorsements=[domain.Category(cat.split('.', 1))
                          for cat in endorsements.split(',')]
        )
    )
    token = auth.tokens.encode(session, app.config['JWT_SECRET'])
    click.echo(token)


if __name__ == '__main__':
    generate_token()
