from fastapi import APIRouter

from app.api.v1.admin.departments.router import (
    router as departments_router,
)
from app.api.v1.admin.events.router import (
    router as events_router,
)
from app.api.v1.admin.organizations.router import (
    router as organizations_router,
)
from app.api.v1.admin.department_details.router import (
    router as department_details_router,
)


router = APIRouter(
    prefix="/admin",
)

router.include_router(organizations_router)
router.include_router(departments_router)
router.include_router(department_details_router)
router.include_router(events_router)