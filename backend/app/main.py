import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import analysis, audit, auth, indexing, knowledge, policies, projects
from app.core.knowledge import KnowledgeGraphManager
from app.db.seed import seed_builtin_templates
from app.db.session import async_session

logger = logging.getLogger("forgeline")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed builtin policy templates
    logger.info("Starting ForgeLine API — seeding builtin templates")
    async with async_session() as db:
        await seed_builtin_templates(db)
    logger.info("Seed complete")

    # Initialize Neo4j knowledge graph manager
    graph = KnowledgeGraphManager()
    try:
        await graph.ensure_indexes()
        status = await graph.verify_connection()
        logger.info("Neo4j connected: %s", status)
    except Exception:
        logger.warning("Neo4j not available — knowledge graph features disabled")
    app.state.graph = graph

    yield

    # Shutdown
    await graph.close()
    logger.info("Shutting down ForgeLine API")


app = FastAPI(title="ForgeLine API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    logger.info("%s %s %s %.1fms", request.method, request.url.path, response.status_code, elapsed)
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(auth.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(policies.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(indexing.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")


@app.get("/health")
async def health():
    neo4j_status = "unknown"
    graph: KnowledgeGraphManager | None = getattr(app.state, "graph", None)
    if graph:
        try:
            await graph.verify_connection()
            neo4j_status = "connected"
        except Exception:
            neo4j_status = "disconnected"
    return {"status": "healthy", "service": "forgeline-api", "neo4j": neo4j_status}
