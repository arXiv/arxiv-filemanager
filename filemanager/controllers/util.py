"""Helpers and utilities for controllers."""

from arxiv.users import domain as auth_domain


def format_user_information_for_logging(user: auth_domain.User) -> str:
    """
    Format user information for logging purposes.

    ``user_id`` is immutable but difficult to interpret. ``username`` is a
    little easier to understand. Centralize formatting to make it easier to
    adjust in the future.

    Parameters
    ----------
    user : :class:`.auth_domain.User`
        Contains user information from auth session.

    Returns
    -------
    str
        String formatted with desired user information.

    """
    return f"user:{user.user_id}:{user.username}"
