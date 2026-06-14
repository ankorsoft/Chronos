"""
API endpoints (views) for Chronos Context.
"""
import os
import hashlib
from pathlib import Path
from fastapi import Depends, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.models import Project, ProjectSnapshot
from app.schemas import (
    SnapshotResponse, ContextResponse, ExportResponse,
    ProjectSettingsResponse, ExportRequest, AnalyzeRequest, InvalidateCacheRequest, ProjectCreate, ProjectResponse
)
from core.engine import analyze_project
from core.cache import AnalysisCache


# ===== Helper functions =====

def _generate_gpt_context(snapshot, project_name: str) -> str:
    return (
        f"# SYSTEM PROMPT FOR {project_name.upper()}\n\n"
        f"You are an expert Python developer working on the '{project_name}' project.\n\n"
        f"## Project Overview\n"
        f"- Total Files: {snapshot.total_files}\n"
        f"- Total Lines: {snapshot.total_lines}\n"
        f"- Original Tokens: {snapshot.original_tokens:,}\n"
        f"- Compressed Tokens: {snapshot.compressed_tokens:,}\n"
        f"- Compression Ratio: {snapshot.compression_ratio}%\n\n"
        f"{snapshot.structure_json}"
    )


def _generate_claude_context(snapshot, project_name: str) -> str:
    return (
        f"<project>{project_name}</project>\n\n"
        f"<overview>\n"
        f"<files>{snapshot.total_files}</files>\n"
        f"<lines>{snapshot.total_lines}</lines>\n"
        f"<original_tokens>{snapshot.original_tokens:,}</original_tokens>\n"
        f"<compressed_tokens>{snapshot.compressed_tokens:,}</compressed_tokens>\n"
        f"</overview>\n\n"
        f"{snapshot.structure_json}"
    )


# ===== Project endpoints =====

def create_project(project: ProjectCreate, session: Session) -> ProjectResponse:
    if not os.path.isdir(project.path):
        raise HTTPException(status_code=400, detail=f"Path does not exist: {project.path}")
    existing = session.exec(select(Project).where(Project.path == project.path)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project with this path already exists")
    db_project = Project(name=project.name, path=project.path)
    session.add(db_project)
    session.commit()
    session.refresh(db_project)
    return db_project


def list_projects(session: Session):
    return session.exec(select(Project)).all()


def get_project(project_id: int, session: Session) -> ProjectResponse:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ===== Settings endpoints =====

def get_project_settings(project_id: int, session: Session) -> ProjectSettingsResponse:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectSettingsResponse(
        project_id=project.id,
        ignored_patterns=project.ignored_patterns,
        output_format=project.output_format,
        priority_modules=project.priority_modules,
    )


def update_project_settings(project_id: int, updates: "ProjectSettingsUpdate", session: Session) -> ProjectSettingsResponse:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if updates.ignored_patterns is not None:
        project.ignored_patterns = updates.ignored_patterns
    if updates.output_format is not None:
        project.output_format = updates.output_format
    if updates.priority_modules is not None:
        project.priority_modules = updates.priority_modules
    session.add(project)
    session.commit()
    session.refresh(project)
    return ProjectSettingsResponse(
        project_id=project.id,
        ignored_patterns=project.ignored_patterns,
        output_format=project.output_format,
        priority_modules=project.priority_modules,
    )


# ===== Snapshot endpoints =====

def get_project_snapshots(project_id: int, session: Session):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    snapshots = session.exec(
        select(ProjectSnapshot)
        .where(ProjectSnapshot.project_id == project_id)
        .order_by(ProjectSnapshot.created_at.desc())
    ).all()
    if not snapshots:
        return []
    return [
        SnapshotResponse(
            id=s.id, project_id=s.project_id, structure=s.structure_json,
            total_files=s.total_files, total_lines=s.total_lines,
            original_tokens=s.original_tokens, compressed_tokens=s.compressed_tokens,
            compression_ratio=s.compression_ratio,
            tokens_saved=s.original_tokens - s.compressed_tokens,
            created_at=s.created_at.isoformat(),
        )
        for s in snapshots
    ]


def get_snapshot(snapshot_id: int, session: Session) -> SnapshotResponse:
    snapshot = session.get(ProjectSnapshot, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    tokens_saved = snapshot.original_tokens - snapshot.compressed_tokens
    return SnapshotResponse(
        id=snapshot.id, project_id=snapshot.project_id, structure=snapshot.structure_json,
        total_files=snapshot.total_files, total_lines=snapshot.total_lines,
        original_tokens=snapshot.original_tokens, compressed_tokens=snapshot.compressed_tokens,
        compression_ratio=snapshot.compression_ratio, tokens_saved=tokens_saved,
        created_at=snapshot.created_at.isoformat(),
    )


# ===== Export endpoint =====

def export_project_context(project_id: int, request: ExportRequest, session: Session) -> ExportResponse:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    snapshot = session.exec(
        select(ProjectSnapshot)
        .where(ProjectSnapshot.project_id == project_id)
        .order_by(ProjectSnapshot.created_at.desc())
    ).first()
    if not snapshot:
        raise HTTPException(status_code=400, detail="No snapshots available for export")

    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")

    if request.format == "txt":
        content = snapshot.structure_json
    elif request.format == "md":
        content = snapshot.structure_json
    elif request.format == "gpt":
        content = _generate_gpt_context(snapshot, project.name)
    elif request.format == "claude":
        content = _generate_claude_context(snapshot, project.name)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported export format: {request.format}")

    return ExportResponse(content=content, format=request.format, tokens_counted=len(enc.encode(content)))


# ===== Context endpoint =====

def get_project_context(project_id: int, session: Session) -> ContextResponse:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    snapshot = session.exec(
        select(ProjectSnapshot)
        .where(ProjectSnapshot.project_id == project_id)
        .order_by(ProjectSnapshot.created_at.desc())
    ).first()
    if not snapshot:
        result = analyze_project(project.path)
        return ContextResponse(structure=result["structure"], metrics=result["metrics"])
    tokens_saved = snapshot.original_tokens - snapshot.compressed_tokens
    return ContextResponse(
        structure=snapshot.structure_json,
        metrics={
            "total_files": snapshot.total_files, "total_lines": snapshot.total_lines,
            "original_tokens": snapshot.original_tokens, "compressed_tokens": snapshot.compressed_tokens,
            "compression_ratio": snapshot.compression_ratio, "tokens_saved": tokens_saved,
        },
    )


def delete_project(project_id: int, session: Session) -> dict:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    snapshots = session.exec(select(ProjectSnapshot).where(ProjectSnapshot.project_id == project_id)).all()
    for s in snapshots:
        session.delete(s)
    session.delete(project)
    session.commit()
    return {"message": f"Project '{project.name}' and all its data deleted"}


# ===== Cache endpoint =====

def invalidate_cache(request: InvalidateCacheRequest, session: Session) -> dict:
    project = session.get(Project, request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    cache = AnalysisCache(project.path)
    cache.invalidate()
    return {"message": f"Cache invalidated for '{project.name}'"}


# ===== Analyze endpoint =====

def get_project_context_with_analyze(project_id: int, session: Session) -> ContextResponse:
    """Get context for a project, analyzing if no snapshot exists."""
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    snapshot = session.exec(
        select(ProjectSnapshot)
        .where(ProjectSnapshot.project_id == project_id)
        .order_by(ProjectSnapshot.created_at.desc())
    ).first()
    if not snapshot:
        result = analyze_project(project.path)
        return ContextResponse(structure=result["structure"], metrics=result["metrics"])
    tokens_saved = snapshot.original_tokens - snapshot.compressed_tokens
    return ContextResponse(
        structure=snapshot.structure_json,
        metrics={
            "total_files": snapshot.total_files, "total_lines": snapshot.total_lines,
            "original_tokens": snapshot.original_tokens, "compressed_tokens": snapshot.compressed_tokens,
            "compression_ratio": snapshot.compression_ratio, "tokens_saved": tokens_saved,
        },
    )


def analyze_project_for_project_id(project_id: int, request: AnalyzeRequest, session: Session, use_cache: bool = True) -> SnapshotResponse:
    """Analyze using project path from DB."""
    if not os.path.isdir(request.project_path):
        raise HTTPException(status_code=400, detail=f"Path does not exist: {request.project_path}")

    result = None
    cache_hit = False

    if use_cache:
        cache = AnalysisCache(request.project_path)
        if cache.is_valid():
            current_hashes = {}
            for py_file in Path(request.project_path).rglob("*.py"):
                if any(p.startswith('.') for p in py_file.parts):
                    continue
                if 'venv' in py_file.parts or '__pycache__' in py_file.parts:
                    continue
                current_hashes[str(py_file.relative_to(request.project_path))] = hashlib.sha256(py_file.read_bytes()).hexdigest()
            needs_update, changed = cache.needs_update(current_hashes)
            if not needs_update:
                cached = cache.get_cached_result()
                if cached:
                    result = cached
                    cache_hit = True

    if result is None:
        result = analyze_project(request.project_path, use_cache=False)

    project = session.exec(select(Project).where(Project.path == request.project_path)).first()
    if not project:
        project_name = os.path.basename(request.project_path) or "Unnamed Project"
        project = Project(name=project_name, path=request.project_path)
        session.add(project)
        session.commit()
        session.refresh(project)

    snapshot = ProjectSnapshot(
        project_id=project.id, structure_json=result["structure"],
        total_files=result["metrics"]["total_files"], total_lines=result["metrics"]["total_lines"],
        original_tokens=result["metrics"]["original_tokens"], compressed_tokens=result["metrics"]["compressed_tokens"],
        compression_ratio=result["metrics"]["compression_ratio"],
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)

    response_data = {
        "id": snapshot.id, "project_id": snapshot.project_id, "structure": snapshot.structure_json,
        "total_files": snapshot.total_files, "total_lines": snapshot.total_lines,
        "original_tokens": snapshot.original_tokens, "compressed_tokens": snapshot.compressed_tokens,
        "compression_ratio": snapshot.compression_ratio, "tokens_saved": result["metrics"]["tokens_saved"],
        "created_at": snapshot.created_at.isoformat(), "cache_hit": cache_hit,
    }
    if cache_hit and result.get("changed_files"):
        response_data["incremental"] = True
        response_data["changed_files_count"] = len(result.get("changed_files", []))

    return SnapshotResponse(**response_data)


def analyze_project_endpoint(request: AnalyzeRequest, session: Session, use_cache: bool = True) -> SnapshotResponse:
    if not os.path.isdir(request.project_path):
        raise HTTPException(status_code=400, detail=f"Path does not exist: {request.project_path}")

    result = None
    cache_hit = False

    if use_cache:
        cache = AnalysisCache(request.project_path)
        if cache.is_valid():
            current_hashes = {}
            for py_file in Path(request.project_path).rglob("*.py"):
                if any(p.startswith('.') for p in py_file.parts):
                    continue
                if 'venv' in py_file.parts or '__pycache__' in py_file.parts:
                    continue
                current_hashes[str(py_file.relative_to(request.project_path))] = hashlib.sha256(py_file.read_bytes()).hexdigest()
            needs_update, changed = cache.needs_update(current_hashes)
            if not needs_update:
                cached = cache.get_cached_result()
                if cached:
                    result = cached
                    cache_hit = True

    if result is None:
        result = analyze_project(request.project_path, use_cache=False)

    project = session.exec(select(Project).where(Project.path == request.project_path)).first()
    if not project:
        project_name = os.path.basename(request.project_path) or "Unnamed Project"
        project = Project(name=project_name, path=request.project_path)
        session.add(project)
        session.commit()
        session.refresh(project)

    snapshot = ProjectSnapshot(
        project_id=project.id, structure_json=result["structure"],
        total_files=result["metrics"]["total_files"], total_lines=result["metrics"]["total_lines"],
        original_tokens=result["metrics"]["original_tokens"], compressed_tokens=result["metrics"]["compressed_tokens"],
        compression_ratio=result["metrics"]["compression_ratio"],
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)

    response_data = {
        "id": snapshot.id, "project_id": snapshot.project_id, "structure": snapshot.structure_json,
        "total_files": snapshot.total_files, "total_lines": snapshot.total_lines,
        "original_tokens": snapshot.original_tokens, "compressed_tokens": snapshot.compressed_tokens,
        "compression_ratio": snapshot.compression_ratio, "tokens_saved": result["metrics"]["tokens_saved"],
        "created_at": snapshot.created_at.isoformat(), "cache_hit": cache_hit,
    }
    if cache_hit and result.get("changed_files"):
        response_data["incremental"] = True
        response_data["changed_files_count"] = len(result.get("changed_files", []))

    return SnapshotResponse(**response_data)


# ===== HTML root endpoint =====

def read_root_html() -> HTMLResponse:
    """Serve the static index.html page."""
    from app.api import STATIC_DIR
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    # Fallback: inline HTML (will be removed after static file is created)
    raise HTTPException(status_code=404, detail="Static index.html not found. Please check the project structure.")