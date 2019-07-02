"""Provides :class:`.ReadinessMixin`."""

from enum import Enum

from dataclasses import dataclass, field

from .errors_and_warnings import ErrorsAndWarningsWorkspace


@dataclass
class ReadinessWorkspace(ErrorsAndWarningsWorkspace):
    """Adds methods and properties releated to source readiness."""

    class Readiness(Enum):
        """
        Upload workspace readiness states.

        Provides an indication (but not the final word) on whether the
        workspace is suitable for incorporating into a submission to arXiv.
        """

        READY = 'READY'
        """Overall state of workspace is good; no warnings/errors reported."""

        READY_WITH_WARNINGS = 'READY_WITH_WARNINGS'
        """
        Workspace is ready, but there are warnings for the user.

        Upload processing reported warnings which do not prohibit client
        from continuing on to compilation and submit steps.
        """

        ERRORS = 'ERRORS'
        """
        There were errors reported while processing upload files.

        Subsequent steps [compilation, submit, publish] should reject working
        with such an upload package.
        """

    lastupload_readiness: Readiness = field(default=Readiness.READY)
    """Content readiness status after last upload event."""

    @property
    def readiness(self) -> 'Readiness':
        """Readiness state of the upload workspace."""
        if self.has_fatal_errors:
            return ReadinessWorkspace.Readiness.ERRORS
        elif self.has_active_warnings:
            return ReadinessWorkspace.Readiness.READY_WITH_WARNINGS
        return ReadinessWorkspace.Readiness.READY