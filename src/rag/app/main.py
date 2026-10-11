import time
import logging
from typing import List
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.rag_chain import build_rag_chain, clear_memory

# ------------------------------------------
# Logging setup
# ------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# ------------------------------------------
# FastAPI app setup
# ------------------------------------------
app = FastAPI()
qa_chain = None
startup_error = None


# ------------------------------------------
# Models
# ------------------------------------------
class QueryRequest(BaseModel):
    query: str


# ------------------------------------------
# Startup: build RAG chain once
# ------------------------------------------
@app.on_event("startup")
async def startup_event():
    """Initialize the RAG chain once when the app starts."""
    global qa_chain, startup_error
    logger.info("Starting up RAG service...")
    try:
        qa_chain = build_rag_chain()
        startup_error = None
        logger.info("RAG chain initialized successfully.")
    except Exception as exc:
        qa_chain = None
        startup_error = str(exc)
        logger.exception(
            "RAG chain initialization failed. Service will stay online, but query handling is unavailable."
        )


# ------------------------------------------
# Middleware for request logging
# ------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = (time.time() - start_time) * 1000  # ms
    logger.info(
        f"{request.method} {request.url.path} status={response.status_code} duration={duration:.2f}ms"
    )
    return response


# ------------------------------------------
# Routes
# ------------------------------------------
@app.get("/healthz")
def healthz():
    logger.debug("Health check endpoint hit.")
    if qa_chain is None:
        return {
            "status": "degraded",
            "reason": "rag_chain_unavailable",
            "error": startup_error,
        }
    return {"status": "ok"}


@app.post("/answer_query")
async def answer_query(req: QueryRequest):
    """Answer a question using the RAG chain."""
    if not req.query:
        logger.warning("Missing 'query' parameter in request.")
        return {"error": "Missing 'query' parameter"}

    if qa_chain is None:
        logger.error("Query received while RAG chain is unavailable.")
        return JSONResponse(
            status_code=503,
            content={
                "error": "RAG chain unavailable. Check service logs and environment variables.",
                "detail": startup_error,
            },
        )

    logger.info("Processing query: %s", req.query[:200])

    try:
        result = qa_chain.invoke({"question": req.query})
        logger.info("Successfully generated answer.")
        return {
            "answer": result.get("answer"),
            "sources": result.get("context")
        }

    except Exception as e:
        logger.error("Error during RAG chain invocation: %s", e, exc_info=True)
        return {"error": "Internal server error"}

@app.post("/clear_rag_memory")
async def clear_rag_memory():
    """Reset the RAG conversation memory."""
    logger.warning("Memory reset endpoint triggered.") 

    try:
        clear_memory()   # from rag_chain.py
        logger.info("Conversation memory cleared successfully.")
        return {"status": "memory_cleared"}

    except Exception as e:
        logger.error("Error clearing memory: %s", e, exc_info=True)
        return {"error": "Internal server error during memory reset"}
