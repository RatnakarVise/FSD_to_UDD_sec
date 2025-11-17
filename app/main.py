from __future__ import annotations

import os
import io
import json
import datetime
import threading
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from fastapi import FastAPI, HTTPException, BackgroundTasks, Response, status, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .rag_loader import load_rag_sections
from .section_mapper import SectionMapper
from .llm_orchestrator import generate_udd_sections
from .docx_builder import build_document
from .config import DEFAULT_RAG_PATH, DEFAULT_MAPPING_PATH


# ============================================================
# LOGGER SETUP
# ============================================================

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

logger = logging.getLogger("FSD_TO_UDD")


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="FSD → UDD Generator (BackgroundTasks style)",
    version="4.0"
)


# ============================================================
# Request Model
# ============================================================

class GenerateRequest(BaseModel):
    fsd_text: str = Field(..., description="Full FSD plain text")
    rag_path: Optional[str] = None
    mapping_path: Optional[str] = None
    document_title: Optional[str] = Field(default="Functional Specification Document")


# ============================================================
# Job management
# ============================================================

_JOBS_LOCK = threading.Lock()
_JOBS: Dict[str, Dict[str, Any]] = {}

def _today_iso() -> str:
    return datetime.date.today().isoformat()


# ============================================================
# UTILITY — Convert pairs to document builder format
# ============================================================

def _pairs_to_builder_structures(
    pairs: List[Tuple[str, str]]
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:

    content_list = []
    sections = []

    for title, text in pairs:
        sections.append({"title": title})
        content_list.append({"section_name": title, "content": text})

    return content_list, sections


# ============================================================
# CORE DOCX GENERATOR (LOGGING ADDED)
# ============================================================

def _generate_docx_bytes(
    fsd_text: str,
    rag_path: str,
    mapping_path: str,
    title: str
) -> bytes:

    trace_id = uuid.uuid4().hex[:8]
    logger.info(f"[{trace_id}] 🔍 Starting DOCX generation")

    # --------------------------------------------------------
    # LOAD RAG
    # --------------------------------------------------------
    logger.info(f"[{trace_id}] Loading RAG file: {rag_path}")
    rag_sections = load_rag_sections(rag_path)
    logger.info(f"[{trace_id}] RAG file loaded with {len(rag_sections)} sections")

    # --------------------------------------------------------
    # LOAD SECTION MAPPER
    # --------------------------------------------------------
    logger.info(f"[{trace_id}] Loading section mapper: {mapping_path}")
    mapper = SectionMapper(mapping_path)
    logger.info(f"[{trace_id}] Mapper loaded successfully")

    # --------------------------------------------------------
    # GENERATE UDD SECTIONS
    # --------------------------------------------------------
    logger.info(f"[{trace_id}] Running generate_udd_sections()")
    pairs: List[Tuple[str, str]] = generate_udd_sections(
        fsd_text,
        rag_sections,
        mapper
    )
    logger.info(f"[{trace_id}] LLM returned {len(pairs)} sections")

    for i, (title, text) in enumerate(pairs):
        status = "FOUND" if text.strip() else "EMPTY/MISSING"
        logger.info(f"[{trace_id}] ▸ Section[{i}] '{title}' — {status}")

    # --------------------------------------------------------
    # CONVERT FORMAT FOR DOCX BUILDER
    # --------------------------------------------------------
    content_list, section_list = _pairs_to_builder_structures(pairs)

    # --------------------------------------------------------
    # BUILD DOCUMENT
    # --------------------------------------------------------
    logger.info(f"[{trace_id}] Building DOCX document...")
    doc = build_document(
        content=content_list,
        sections=section_list,
        flow_diagram_agent=None,
        diagram_dir="diagrams"
    )
    logger.info(f"[{trace_id}] DOCX build completed")

    # --------------------------------------------------------
    # RETURN BYTES
    # --------------------------------------------------------
    buff = io.BytesIO()
    doc.save(buff)
    buff.seek(0)

    logger.info(f"[{trace_id}] DOCX bytes ready for output")

    return buff.read()


# ============================================================
# BACKGROUND JOB RUNNER
# ============================================================

def _run_job(job_id: str, req: GenerateRequest) -> None:

    logger.info(f"🟦 Job {job_id}: STARTED")

    with _JOBS_LOCK:
        _JOBS[job_id]["status"] = "running"
        _JOBS[job_id]["attempts"] = 1

    rag_path = req.rag_path or DEFAULT_RAG_PATH
    mapping_path = req.mapping_path or DEFAULT_MAPPING_PATH

    try:
        logger.info(f"🟦 Job {job_id}: Generating DOCX...")
        docx_bytes = _generate_docx_bytes(
            req.fsd_text,
            rag_path,
            mapping_path,
            req.document_title or "Functional Specification Document"
        )

        out_dir = Path("jobs") / job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "UDD.docx"

        with open(out_path, "wb") as f:
            f.write(docx_bytes)

        with _JOBS_LOCK:
            _JOBS[job_id]["status"] = "done"
            _JOBS[job_id]["result_path"] = str(out_path)
            _JOBS[job_id]["error"] = None

        logger.info(f"🟩 Job {job_id}: COMPLETED")

    except Exception as e:
        logger.exception(f"🟥 Job {job_id}: ERROR")
        with _JOBS_LOCK:
            _JOBS[job_id]["status"] = "done"
            _JOBS[job_id]["result_path"] = None
            _JOBS[job_id]["error"] = str(e)


# ============================================================
# ENDPOINTS (LOGGING ADDED)
# ============================================================

@app.get("/healthz")
def healthz():
    logger.info("Health check requested")
    return {"ok": True, "date": _today_iso()}


@app.post("/generate_direct")
def generate_direct(req: GenerateRequest):

    logger.info("Direct generation request received")

    rag_path = req.rag_path or DEFAULT_RAG_PATH
    mapping_path = req.mapping_path or DEFAULT_MAPPING_PATH

    docx_bytes = _generate_docx_bytes(
        req.fsd_text,
        rag_path,
        mapping_path,
        req.document_title or "Functional Specification Document"
    )

    tmp_dir = Path("jobs") / "direct"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / f"UDD_{_today_iso()}.docx"

    with open(out_path, "wb") as f:
        f.write(docx_bytes)

    logger.info(f"Direct DOCX generated at {out_path}")

    return FileResponse(
        str(out_path),
        media_type=(
            "application/vnd.openxmlformats-"
            "officedocument.wordprocessingml.document"
        ),
        filename=out_path.name,
    )


@app.post("/generate")
def generate(req: GenerateRequest, background_tasks: BackgroundTasks):
    job_id = os.urandom(8).hex()
    logger.info(f"Job request received → Job ID: {job_id}")

    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "status": "pending",
            "attempts": 0,
            "result_path": None,
            "error": None,
        }

    background_tasks.add_task(_run_job, job_id, req)
    logger.info(f"Job {job_id} queued")

    return {"job_id": job_id}


@app.get("/generate/{job_id}")
def get_job(job_id: str, response: Response):
    logger.info(f"Job status requested → Job: {job_id}")

    with _JOBS_LOCK:
        job = _JOBS.get(job_id)

    if not job:
        logger.error(f"Job {job_id} not found")
        raise HTTPException(status_code=404, detail="job_id not found")

    if job["status"] == "done":
        if job.get("result_path") and os.path.exists(job["result_path"]):
            p = Path(job["result_path"])
            logger.info(f"Job {job_id} complete → returning file")
            return FileResponse(
                str(p),
                media_type=(
                    "application/vnd.openxmlformats-"
                    "officedocument.wordprocessingml.document"
                ),
                filename=p.name,
            )
        logger.info(f"Job {job_id} complete with ERROR")
        return {"status": "done", "error": job.get("error")}

    response.status_code = status.HTTP_202_ACCEPTED
    logger.info(f"Job {job_id} still running")
    return {"status": job["status"], "attempts": job.get("attempts", 0)}

