"""Describes the data that will be passed around inside of the service."""

from datetime import datetime
from typing import Type, Any, Optional


class Property(object):
    """Describes a named, typed property on a data structure."""

    def __init__(self, name: str, klass: Optional[Type] = None,
                 default: Any = None) -> None:
        """Set the name, type, and default value for the property."""
        self._name = name
        self.klass = klass
        self.default = default

    def __get__(self, instance: Any, owner: Optional[Type] = None) -> Any:
        """
        Retrieve the value of property from the data instance.

        Parameters
        ----------
        instance : object
            The data structure instance on which the property is set.
        owner : type
            The class/type of ``instance``.

        Returns
        -------
        object
            If the data structure is instantiated, returns the value of this
            property. Otherwise returns this :class:`.Property` instance.
        """
        if instance:
            if self._name not in instance.__dict__:
                instance.__dict__[self._name] = self.default
            return instance.__dict__[self._name]
        return self

    def __set__(self, instance: Any, value: Any) -> None:
        """
        Set the value of the property on the data instance.

        Parameters
        ----------
        instance : object
            The data structure instance on which the property is set.
        value : object
            The value to which the property should be set.

        Raises
        ------
        TypeError
            Raised when ``value`` is not an instance of the specified type
            for the property.
        """
        if self.klass is not None and not isinstance(value, self.klass):
            raise TypeError('Must be an %s' % self.klass.__name__)
        instance.__dict__[self._name] = value


class Data(object):
    """Base class for data domain classes."""

    def __init__(self, **data: Any) -> None:
        """Initialize with some data."""
        for key, value in data.items():
            if isinstance(getattr(self.__class__, key), Property):
                setattr(self, key, value)

class Upload(Data):
    """All information about an upload."""

    # Various state settings

    # Upload workspace is actively being used.
    ACTIVE = 'ACTIVE'
    # Client/Admin/System indicate release to indicate upload workspace is no
    # longer user.
    RELEASED = 'RELEASED'
    # After upload workspace files are deleted the state of workspace in
    # database is set to deleted. Database entry is retained indefinitely.
    DELETED = 'DELETED'

    # Indicates upload workspace is lock and cannot be updated. The workspace
    # might be locked during publish or when admins are updating uploaded
    # files.
    LOCKED = 'LOCKED'
    # When workspace is unlocked updates are allowed (workspace is normally
    # in this state).
    UNLOCKED = 'UNLOCKED'

    # Overall state of upload files is good with no warnings or errors
    # reported.
    READY = 'READY'
    # Upload processing reported warnings which do not prohibit client
    # from continuing on to compilation and submit steps.
    READY_WITH_WARNINGS = 'READY_WITH_WARNINGS'

    # There were errors reported while processing upload files. Subsequent
    # steps [compilation, submit, publish] should reject working with such
    # an upload package.
    ERRORS = 'ERRORS'


    upload_id = Property('upload_id', int)

    submission_id = Property('submission_id', str)
    """Optionally associate upload workspace with submission_id.
       File Management Service 'upload_id' is independent and not directly
       tied to any external service."""

    owner_user_id = Property('owner_user_id', str)
    """User id for owner of workspace."""

    archive = Property('archive', str)
    """Target archive for this submission."."""

    created_datetime = Property('created_datetime', datetime)
    """When workspace was created"""

    modified_datetime = Property('modified_datetime', datetime)
    """When workspace was last modified"""

    # Data about last upload

    lastupload_start_datetime = Property('lastupload_start_datetime ', datetime)
    """When we started processing last upload event."""

    lastupload_completion_datetime = Property('lastupload_completion_datetime', datetime)
    """When we completed processing last upload event."""

    lastupload_logs = Property('lastupload_logs', str)
    """Logs associated with last upload event."""

    lastupload_file_summary = Property('lastupload_file_summary', str)
    """Logs associated with last upload event."""

    lastupload_upload_status = Property('lastupload_upload_status', str)
    """Content eadiness status after last upload event."""

    # General state of upload

    state = Property('state', str)
    """Status of upload. 'ACTIVE', 'RELEASED', 'DELETED'
    Eventually will become enumeration."""

    lock = Property('lock', str)
    """Lock state of upload workspace. 'LOCKED', 'UNLOCKED'"""
