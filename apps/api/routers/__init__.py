from fastapi import APIRouter

from . import ga, intelligence, performance, stream, trades

router = APIRouter(prefix="/api/v1")
router.include_router(performance.router)
router.include_router(trades.router)
router.include_router(ga.router)
router.include_router(stream.router)
router.include_router(intelligence.router)
