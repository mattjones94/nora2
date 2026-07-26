from fastapi import APIRouter

from app.api.v1.admin.router import router as admin_router
from app.api.v1.chat.router import router as chat_router


router = APIRouter(
    prefix="/api/v1",
)

router.include_router(admin_router)
router.include_router(chat_router)