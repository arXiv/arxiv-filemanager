"""Helpers for :mod:`.domain.uploads`."""

from typing import Callable, Any, TypeVar, cast
from datetime import datetime
from functools import wraps

from pytz import UTC
from typing_extensions import Protocol

from arxiv.base import logging

logger = logging.getLogger('filemanager.domain.uploads')
logger.propagate = False

TFun = TypeVar('TFun', bound=Callable[..., Any])


class _IWorkspace(Protocol):
    """Interface for the upload workspace, from the perspective of this mod."""

    modified_datetime: datetime


# This is implemented as a class per
# https://github.com/python/mypy/issues/1551#issuecomment-253978622.
class modifies_workspace:
    """Extend an instance method to perform post-modification steps."""

    def __call__(self, func: TFun) -> TFun:
        """Decorate a :class:`.Workspace` method."""
        @wraps(func)
        def inner(workspace: _IWorkspace, *args: Any, **kwargs: Any) \
                -> Any:
            result = func(workspace, *args, **kwargs)
            workspace.modified_datetime = datetime.now(UTC)
            return result
        return cast(TFun, inner)