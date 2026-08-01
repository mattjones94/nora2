from fastapi import APIRouter

from app.features.conversation_logs.admin_router import (
    router as conversation_logs_router,
)
from app.features.department_details.admin_router import (
    router as department_details_router,
)
from app.features.departments.admin_router import (
    router as departments_router,
)
from app.features.events.admin_router import (
    router as events_router,
)
from app.features.organizations.admin_router import (
    router as organizations_router,
)
from app.features.resources.admin_router import (
    router as resources_router,
)


router = APIRouter(
    prefix="/admin",
)

router.include_router(
    organizations_router
)

router.include_router(
    departments_router
)

router.include_router(
    department_details_router
)

router.include_router(
    events_router
)

router.include_router(
    resources_router
)

router.include_router(
    conversation_logs_router
)