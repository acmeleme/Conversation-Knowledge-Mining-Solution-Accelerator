"""
FastAPI application entry point for the Conversation Knowledge Mining Solution Accelerator.

This module sets up the FastAPI app, configures middleware, loads environment variables,
registers API routers, and manages application lifespan events such as agent initialization
and cleanup.
"""


from contextlib import asynccontextmanager
import os
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dotenv import load_dotenv
import uvicorn

from agents.conversation_agent_factory import ConversationAgentFactory
from agents.search_agent_factory import SearchAgentFactory
from agents.sql_agent_factory import SQLAgentFactory
from agents.chart_agent_factory import ChartAgentFactory
from api.api_routes import router as backend_router
from api.history_routes import router as history_router
from helpers.content_safety_helper import build_audit_log_entry

load_dotenv()


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """
    Manages the application lifespan events for the FastAPI app.

    On startup, initializes the Azure AI agent using the configuration and attaches it to the app state.
    On shutdown, deletes the agent instance and performs any necessary cleanup.
    """
    fastapi_app.state.agent = await ConversationAgentFactory.get_agent()
    fastapi_app.state.search_agent = await SearchAgentFactory.get_agent()
    fastapi_app.state.sql_agent = await SQLAgentFactory.get_agent()
    fastapi_app.state.chart_agent = await ChartAgentFactory.get_agent()
    yield
    await ConversationAgentFactory.delete_agent()
    await SearchAgentFactory.delete_agent()
    await SQLAgentFactory.delete_agent()
    await ChartAgentFactory.delete_agent()
    fastapi_app.state.sql_agent = None
    fastapi_app.state.search_agent = None
    fastapi_app.state.agent = None
    fastapi_app.state.chart_agent = None


def build_app() -> FastAPI:
    """
    Creates and configures the FastAPI application instance.
    """
    fastapi_app = FastAPI(
        title="Conversation Knowledge Mining Solution Accelerator",
        version="1.0.0",
        lifespan=lifespan
    )

    allowed_origins = os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "https://app-financeirax01.azurewebsites.net",
    ).split(",")

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @fastapi_app.middleware("http")
    async def phase4_content_safety_middleware(request: Request, call_next):
        user_id = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME") or "anonymous"
        content_safety_result = request.headers.get("X-Content-Safety-Result") or "SAFE"
        request_id = (
            request.headers.get("X-APIM-Request-Id")
            or request.headers.get("X-Request-Id")
            or str(uuid4())
        )
        audit_log_entry = build_audit_log_entry(
            user_id=user_id,
            request_id=request_id,
            content_safety_result=content_safety_result,
            endpoint=request.url.path,
        )
        request.state.audit_log_entry = audit_log_entry

        if content_safety_result.startswith("BLOCKED:"):
            category = content_safety_result.split(":", 1)[1] or "Unknown"
            response = JSONResponse(
                status_code=400,
                content={
                    "error": "Content blocked by Azure AI Content Safety.",
                    "code": "CONTENT_SAFETY_VIOLATION",
                    "category": category,
                    "requestId": request_id,
                },
            )
        else:
            response = await call_next(request)

        response.headers["X-Audit-UserId"] = audit_log_entry["user_id"]
        response.headers["X-Audit-Timestamp"] = audit_log_entry["timestamp"]
        response.headers["X-Content-Safety-Result"] = audit_log_entry["content_safety_result"]
        response.headers["X-APIM-Version"] = request.headers.get("X-APIM-Version", "3.0")
        return response

    # Include routers
    fastapi_app.include_router(backend_router, prefix="/api", tags=["backend"])
    fastapi_app.include_router(history_router, prefix="/history", tags=["history"])

    @fastapi_app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy"}

    return fastapi_app


app = build_app()


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
