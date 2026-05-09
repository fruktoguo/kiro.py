"""Anthropic API 路由配置 - 参考 src/anthropic/router.rs"""

from fastapi import APIRouter, Request

from .handlers import count_tokens, get_models, post_messages, post_messages_cc
from .middleware import AppState, AuthMiddleware, add_cors_middleware
from .types import CountTokensRequest, MessagesRequest

MAX_BODY_SIZE = 50 * 1024 * 1024  # 50MB


def create_router() -> APIRouter:
    """创建 Anthropic API 路由"""
    router = APIRouter()

    # /v1 路由
    router.add_api_route("/v1/models", get_models, methods=["GET"])
    router.add_api_route("/v1/messages", post_messages, methods=["POST"])
    router.add_api_route("/v1/messages/count_tokens", count_tokens, methods=["POST"])

    # /cc/v1 路由（Claude Code 兼容端点）
    router.add_api_route("/cc/v1/messages", post_messages_cc, methods=["POST"])
    router.add_api_route("/cc/v1/messages/count_tokens", count_tokens, methods=["POST"])

    return router


def create_router_with_provider(api_key: str, provider=None, extract_thinking: bool = True) -> APIRouter:
    """创建带 Provider 的 Anthropic API 路由（供 main.py 使用）

    注意: profile_arn 不再传入，由 provider 层根据实际凭据动态注入到请求体。
    """
    router = create_router()
    # 将 state 附加到 router，main.py 负责挂载中间件
    router.state = AppState(api_key=api_key, kiro_provider=provider, extract_thinking=extract_thinking)
    return router


def setup_anthropic_routes(app, api_key: str, kiro_provider=None, extract_thinking: bool = True):
    """配置 Anthropic API 路由到 FastAPI 应用"""
    state = AppState(api_key=api_key, kiro_provider=kiro_provider, extract_thinking=extract_thinking)

    router = create_router()
    app.include_router(router)

    # 添加认证中间件
    app.add_middleware(AuthMiddleware, state=state)

    # 添加 CORS
    add_cors_middleware(app)
