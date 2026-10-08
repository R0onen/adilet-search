from fastapi import APIRouter

from app.api.v1 import admin, answer, documents, feedback, health, search

API_PREFIX = "/api/v1"

router = APIRouter(prefix=API_PREFIX)
for module in (search, answer, documents, feedback, health, admin):
    router.include_router(module.router)
