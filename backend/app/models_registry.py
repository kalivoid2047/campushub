"""Imports every module's ORM models so Base.metadata is complete.

Used by Alembic (migrations/env.py) and by tests that create the schema.
Add an import line here whenever a new module gains models.
"""

from app.shared.base import Base  # noqa: F401
from app.modules.iam import models as iam_models  # noqa: F401
from app.modules.admin import models as admin_models  # noqa: F401
from app.modules.sync import models as sync_models  # noqa: F401
from app.modules.resources import models as resources_models  # noqa: F401
from app.modules.communication import models as communication_models  # noqa: F401
from app.modules.assignments import models as assignments_models  # noqa: F401
from app.modules.virtual_classroom import models as virtual_classroom_models  # noqa: F401
from app.modules.attendance import models as attendance_models  # noqa: F401
