"""SQLAlchemy ORM models for the Upload service."""

from sqlalchemy import Column, DateTime, Integer, String, Text, JSON
from flask_sqlalchemy import SQLAlchemy, Model

db: SQLAlchemy = SQLAlchemy()


class DBUpload(db.Model):
    """Model for uploads."""

    __tablename__ = 'uploads'
    upload_id = Column(Integer, primary_key=True)
    """The unique identifier for a thing."""
    submission_id = Column(Integer)
    """Submission identifier (optional)"""
    name = Column(String(255))
    """Note/comment/metadata about the upload."""
    created_datetime = Column(DateTime)
    """The datetime when the upload was created."""
    modified_datetime = Column(DateTime, nullable=True)
    """The datetime when the upload was last created."""
    lastupload_start_datetime = Column(DateTime, nullable=True)
    """Start datetime of last upload."""
    lastupload_completion_datetime = Column(DateTime, nullable=True)
    """Completion datetime of last upload."""
    lastupload_logs = Column(Text, nullable=True)
    """Log (error/warning messages) from last upload."""
    lastupload_file_summary = Column(Text, nullable=True)
    """Upload details useful for display in UI"""
    state = Column(String(30), default='Active')
    """State of upload. Initialized. Active. Released."""