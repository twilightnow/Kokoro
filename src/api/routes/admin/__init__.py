"""
Admin API 路由包。

汇总所有 /admin/* 子路由，统一注册到主应用。
每个子模块只处理自己负责的 URL 前缀，不跨模块耦合。
"""
from fastapi import APIRouter

from . import characters, memories, logs, stats, debug, config_mgr

router = APIRouter(prefix="/admin", tags=["admin"])

router.include_router(characters.router)
router.include_router(memories.router)
router.include_router(logs.router)
router.include_router(stats.router)
router.include_router(debug.router)
router.include_router(config_mgr.router)
