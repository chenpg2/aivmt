"""病历录入门户 (teacher-facing case-entry portal).

A zero-build, offline-friendly FastAPI app that lets a clinical collaborator
author/edit standardized-patient cases through a Chinese web form, without
touching YAML. Validation truth lives in :mod:`aivmt.case_schema` /
:mod:`aivmt.case_lint`; the portal never invents clinical content — empty
optional clinical fields are stored as the ``TODO_COLLAB`` placeholder.
"""

from .app import create_app
from .storage import CaseExistsError, CaseStore, PortalStorageError, default_case_dir

__all__ = [
    "create_app",
    "CaseStore",
    "CaseExistsError",
    "PortalStorageError",
    "default_case_dir",
]
