from fastapi import APIRouter, Depends

from app.api.deps import admin_credentials
from app.api.v1.admin import auth, queries, reindex, stats, system

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(auth.router)

_protected = APIRouter(dependencies=[Depends(admin_credentials)])
for module in (stats, queries, system, reindex):
    _protected.include_router(module.router)
router.include_router(_protected)
