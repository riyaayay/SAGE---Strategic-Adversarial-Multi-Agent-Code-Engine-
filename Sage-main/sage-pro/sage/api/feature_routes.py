"""
SAGE-PRO v3 Feature API Routes
═══════════════════════════════
REST endpoints for the 5 new features:
  1. /v1/preview/*       — Live Rendering Engine (Glass)
  2. /v1/vision/*        — Vision Debugging
  3. /v1/timeline/*      — Time-Travel Branching
  4. /v1/lsp/*           — LSP Bridge (Semantic Codebase Awareness)
  5. /v1/dreamer/*       — Chaos Dreamer (Autonomous Self-Improvement)
"""

import asyncio
import structlog
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["sage-v3-features"])

# ── Lazy-initialized singletons ──────────────────────────────────────

_live_renderer = None
_vision_debugger = None
_time_travel = None
_lsp_bridge = None
_chaos_dreamer = None


def _get_renderer():
    global _live_renderer
    if _live_renderer is None:
        from sage.core.live_renderer import LiveRenderer
        _live_renderer = LiveRenderer()
    return _live_renderer


def _get_vision():
    global _vision_debugger
    if _vision_debugger is None:
        from sage.core.vision_debugger import VisionDebugger
        _vision_debugger = VisionDebugger()
    return _vision_debugger


def _get_timeline():
    global _time_travel
    if _time_travel is None:
        from sage.core.time_travel import TimeTravelEngine
        _time_travel = TimeTravelEngine()
    return _time_travel


def _get_lsp():
    global _lsp_bridge
    if _lsp_bridge is None:
        from sage.tools.lsp_bridge import LSPBridge
        _lsp_bridge = LSPBridge()
    return _lsp_bridge


def _get_dreamer():
    global _chaos_dreamer
    if _chaos_dreamer is None:
        from sage.core.chaos_dreamer import ChaosDreamer
        _chaos_dreamer = ChaosDreamer(hyperparams={})
    return _chaos_dreamer


# ═══════════════════════════════════════════════════════════════════
#  Feature 1: Live Rendering Engine (Glass)
# ═══════════════════════════════════════════════════════════════════

class RenderRequest(BaseModel):
    code: str
    session_id: str = "default"


@router.post("/preview/render")
async def render_preview(req: RenderRequest) -> JSONResponse:
    """Renders agent-generated code into a live preview."""
    renderer = _get_renderer()
    previews = await renderer.render(req.code, req.session_id)
    return JSONResponse({"previews": previews})


@router.get("/preview/{preview_id}")
async def get_preview(preview_id: str) -> HTMLResponse:
    """Serves a rendered preview as HTML (for iframe embedding)."""
    from sage.core.live_renderer import get_preview
    html_content = get_preview(preview_id)
    if html_content is None:
        raise HTTPException(status_code=404, detail="Preview not found")
    return HTMLResponse(content=html_content)


# ═══════════════════════════════════════════════════════════════════
#  Feature 2: Vision Debugging
# ═══════════════════════════════════════════════════════════════════

class VisionDebugRequest(BaseModel):
    image_data_uri: str
    user_description: str = ""
    relevant_code: str = ""


@router.post("/vision/debug")
async def vision_debug(req: VisionDebugRequest) -> JSONResponse:
    """Analyzes a screenshot for visual bugs and suggests fixes."""
    debugger = _get_vision()
    result = await debugger.analyze_screenshot(
        image_data_uri=req.image_data_uri,
        user_description=req.user_description,
        relevant_code=req.relevant_code,
    )
    return JSONResponse(result)


@router.post("/vision/debug-upload")
async def vision_debug_upload(
    file: UploadFile = File(...),
    description: str = Form(""),
    code: str = Form(""),
) -> JSONResponse:
    """Upload a screenshot file for visual debugging."""
    debugger = _get_vision()
    image_bytes = await file.read()
    mime = file.content_type or "image/png"
    data_uri = debugger.encode_image_bytes(image_bytes, mime)
    result = await debugger.analyze_screenshot(
        image_data_uri=data_uri,
        user_description=description,
        relevant_code=code,
    )
    return JSONResponse(result)


# ═══════════════════════════════════════════════════════════════════
#  Feature 3: Time-Travel Branching
# ═══════════════════════════════════════════════════════════════════

@router.get("/timeline/{thread_id}")
async def get_timeline(thread_id: str, branch_id: Optional[str] = None) -> JSONResponse:
    """Returns the execution timeline for a thread."""
    tt = _get_timeline()
    timeline = tt.get_timeline(thread_id, branch_id)
    return JSONResponse({"thread_id": thread_id, "timeline": timeline})


@router.get("/timeline/{thread_id}/checkpoint/{checkpoint_id}")
async def get_checkpoint(thread_id: str, checkpoint_id: str) -> JSONResponse:
    """Returns the full state at a specific checkpoint."""
    tt = _get_timeline()
    state = tt.get_checkpoint_state(checkpoint_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return JSONResponse({"checkpoint_id": checkpoint_id, "state": state})


class BranchRequest(BaseModel):
    name: str
    fork_checkpoint_id: str
    description: str = ""


@router.post("/timeline/branch")
async def create_branch(req: BranchRequest) -> JSONResponse:
    """Creates a new branch from a historical checkpoint."""
    tt = _get_timeline()
    try:
        branch = tt.create_branch(req.name, req.fork_checkpoint_id, req.description)
        return JSONResponse({
            "branch_id": branch.branch_id,
            "name": branch.name,
            "forked_from": branch.fork_checkpoint_id,
        })
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/timeline/branches/all")
async def list_branches() -> JSONResponse:
    """Lists all branches."""
    tt = _get_timeline()
    return JSONResponse({"branches": tt.get_branches()})


class DiffRequest(BaseModel):
    checkpoint_a: str
    checkpoint_b: str


@router.post("/timeline/diff")
async def diff_checkpoints(req: DiffRequest) -> JSONResponse:
    """Compares two checkpoint states."""
    tt = _get_timeline()
    diff = tt.diff_checkpoints(req.checkpoint_a, req.checkpoint_b)
    return JSONResponse(diff)


class RewindRequest(BaseModel):
    thread_id: str
    checkpoint_id: str


@router.post("/timeline/rewind")
async def rewind_timeline(req: RewindRequest) -> JSONResponse:
    """Rewinds a thread to a specific checkpoint."""
    tt = _get_timeline()
    try:
        state = tt.rewind_to(req.thread_id, req.checkpoint_id)
        return JSONResponse({"rewound_to": req.checkpoint_id, "state_keys": list(state.keys())})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
#  Feature 4: LSP Bridge
# ═══════════════════════════════════════════════════════════════════

class LSPReferenceRequest(BaseModel):
    symbol: str
    file_path: str
    line: int
    column: int


@router.post("/lsp/references")
async def lsp_find_references(req: LSPReferenceRequest) -> JSONResponse:
    """Finds all references to a symbol."""
    lsp = _get_lsp()
    refs = await lsp.find_references(req.symbol, req.file_path, req.line, req.column)
    return JSONResponse({"references": refs, "count": len(refs)})


class LSPLocationRequest(BaseModel):
    file_path: str
    line: int
    column: int


@router.post("/lsp/definition")
async def lsp_goto_definition(req: LSPLocationRequest) -> JSONResponse:
    """Finds the definition of a symbol."""
    lsp = _get_lsp()
    defs = await lsp.goto_definition(req.file_path, req.line, req.column)
    return JSONResponse({"definitions": defs})


class LSPRenameRequest(BaseModel):
    file_path: str
    line: int
    column: int
    new_name: str


@router.post("/lsp/rename")
async def lsp_rename(req: LSPRenameRequest) -> JSONResponse:
    """Computes a rename refactoring."""
    lsp = _get_lsp()
    result = await lsp.rename_symbol(req.file_path, req.line, req.column, req.new_name)
    return JSONResponse(result)


@router.get("/lsp/diagnostics/{file_path:path}")
async def lsp_diagnostics(file_path: str) -> JSONResponse:
    """Gets diagnostics for a file."""
    lsp = _get_lsp()
    diags = await lsp.get_diagnostics(file_path)
    return JSONResponse({"file": file_path, "diagnostics": diags})


@router.get("/lsp/symbols")
async def lsp_project_symbols() -> JSONResponse:
    """Scans the project for all top-level symbols."""
    lsp = _get_lsp()
    symbols = await lsp.get_project_symbols()
    return JSONResponse({"symbols": symbols, "count": len(symbols)})


# ═══════════════════════════════════════════════════════════════════
#  Feature 5: Chaos Dreamer
# ═══════════════════════════════════════════════════════════════════

@router.post("/dreamer/dream")
async def trigger_dream_cycle() -> JSONResponse:
    """Triggers a single dream cycle (synchronous)."""
    dreamer = _get_dreamer()
    if dreamer.is_dreaming:
        raise HTTPException(status_code=409, detail="Already dreaming")
    report = await dreamer.dream_cycle()
    return JSONResponse(report)


@router.post("/dreamer/start")
async def start_dreaming() -> JSONResponse:
    """Starts continuous background dreaming."""
    dreamer = _get_dreamer()
    if dreamer.is_dreaming:
        raise HTTPException(status_code=409, detail="Already dreaming")
    asyncio.create_task(dreamer.start_background_dreaming())
    return JSONResponse({"status": "dreaming_started"})


@router.post("/dreamer/stop")
async def stop_dreaming() -> JSONResponse:
    """Stops background dreaming."""
    dreamer = _get_dreamer()
    dreamer.stop_dreaming()
    return JSONResponse({"status": "stop_requested"})


@router.get("/dreamer/stats")
async def dreamer_stats() -> JSONResponse:
    """Returns dreaming statistics."""
    dreamer = _get_dreamer()
    return JSONResponse(dreamer.get_stats())


@router.get("/dreamer/challenge")
async def generate_challenge(difficulty: Optional[str] = None) -> JSONResponse:
    """Generates a random synthetic coding challenge."""
    dreamer = _get_dreamer()
    challenge = dreamer.generate_challenge(difficulty)
    return JSONResponse(challenge)
