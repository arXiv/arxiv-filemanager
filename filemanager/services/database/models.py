"""SQLAlchemy ORM models for the Upload service."""

from typing import Optional

import sqlalchemy.types as types
from sqlalchemy import Column, DateTime, Integer, String, Text, JSON
from flask_sqlalchemy import SQLAlchemy, Model

from arxiv.util.serialize import dumps, loads

from ...domain import Workspace, LockState, SourceType, Status


db: SQLAlchemy = SQLAlchemy()


class FriendlyJSONType(types.TypeDecorator):
    """A SQLite-friendly JSON data type."""

    impl = types.TEXT

    def process_bind_param(self, obj: Optional[dict], dialect: str) \
            -> Optional[str]:
        """Serialize a dict to JSON."""
        if obj is not None:
            value: str = dumps(obj)
            return value
        return obj

    def process_result_value(self, value: str, dialect: str) -> Optional[dict]:
        """Deserialize JSON content to a dict."""
        if value is not None:
            obj: dict = loads(value)
            return obj
        return None


# SQLite does not support JSON, so we extend JSON to use our custom data type
# as a variant for the 'sqlite' dialect.
FriendlyJSON = JSON().with_variant(FriendlyJSONType, 'sqlite')


class DBUpload(db.Model):
    """Model for uploads."""

    __tablename__ = 'uploads'

    upload_id = Column(Integer, primary_key=True)
    """The unique identifier for the upload workspace."""

    owner_user_id = Column(String(255))
    """Owner of upload workspace."""

    created_datetime = Column(DateTime)
    """The datetime when the upload was created."""

    modified_datetime = Column(DateTime, nullable=True)
    """The datetime when the upload was last created."""

    files = Column(FriendlyJSON)
    errors = Column(FriendlyJSON)

    last_upload_start_datetime = Column(DateTime, nullable=True)
    """Start datetime of last upload."""

    last_upload_completion_datetime = Column(DateTime, nullable=True)
    """Completion datetime of last upload."""

    last_upload_logs = Column(Text, nullable=True)
    """Log (error/warning messages) from last upload."""

    last_upload_file_summary = Column(Text, nullable=True)
    """Upload details useful for display in UI"""

    last_upload_readiness = Column(Text, nullable=True)
    """Upload content readiness status."""

    status = Column(String(30), default=Status.ACTIVE.value)
    """State of upload. ACTIVE, RELEASED, DELETED"""

    lock_state = Column(String(30), default=LockState.UNLOCKED.value)
    """Lock state of upload workspace. UNLOCKED or LOCKED."""

    source_type = Column(String(30), default=SourceType.UNKNOWN.value)
