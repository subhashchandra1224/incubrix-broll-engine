"""SQLAlchemy ORM models.

Model classes are imported into this package so that ``Base.metadata.create_all``
discovers them.
"""
from app.models.job import Job

__all__ = ["Job"]
