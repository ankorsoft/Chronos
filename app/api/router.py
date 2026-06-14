"""
API routers for Chronos Context.
"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.database import get_session
from app.api.views import (
    create_project, list_projects, get_project, delete_project,
    get_project_settings, update_project_settings,
    get_project_snapshots, get_snapshot,
    export_project_context,
    get_project_context,
    invalidate_cache,
    analyze_project_endpoint,
    read_root_html,
)
from app.schemas import (
    ProjectCreate, ProjectResponse, SnapshotResponse, ContextResponse,
    ExportRequest, ExportResponse, AnalyzeRequest, InvalidateCacheRequest,
    ProjectSettingsUpdate, ProjectSettingsResponse,
)

router = APIRouter()


# ===== Root =====
@router.get("/")
async def root():
    return read_root_html()


# ===== Projects =====
@router.post("/projects", response_model=ProjectResponse, tags=["Projects"])
async def post_project(project: ProjectCreate, session: Session = Depends(get_session)):
    return create_project(project, session)


@router.get("/projects", response_model=list[ProjectResponse], tags=["Projects"])
async def get_projects(session: Session = Depends(get_session)):
    return list_projects(session)


@router.get("/projects/{project_id}", response_model=ProjectResponse, tags=["Projects"])
async def get_project_by_id(project_id: int, session: Session = Depends(get_session)):
    return get_project(project_id, session)


@router.delete("/projects/{project_id}", tags=["Projects"])
async def delete_project_endpoint(project_id: int, session: Session = Depends(get_session)):
    return delete_project(project_id, session)


# ===== Settings =====
@router.get("/projects/{project_id}/settings", response_model=ProjectSettingsResponse, tags=["Settings"])
async def get_settings(project_id: int, session: Session = Depends(get_session)):
    return get_project_settings(project_id, session)


@router.put("/projects/{project_id}/settings", response_model=ProjectSettingsResponse, tags=["Settings"])
async def update_settings(project_id: int, updates: ProjectSettingsUpdate, session: Session = Depends(get_session)):
    return update_project_settings(project_id, updates, session)


# ===== Snapshots =====
@router.get("/projects/{project_id}/snapshots", response_model=list[SnapshotResponse], tags=["Snapshots"])
async def get_snapshots(project_id: int, session: Session = Depends(get_session)):
    return get_project_snapshots(project_id, session)


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotResponse, tags=["Snapshots"])
async def get_snapshot_endpoint(snapshot_id: int, session: Session = Depends(get_session)):
    return get_snapshot(snapshot_id, session)


# ===== Analysis =====
@router.get("/projects/{project_id}/context", response_model=ContextResponse, tags=["Analysis"])
async def get_context(project_id: int, session: Session = Depends(get_session)):
    return get_project_context(project_id, session)


@router.post("/analyze", response_model=SnapshotResponse, tags=["Analysis"])
async def analyze(
    request: AnalyzeRequest,
    session: Session = Depends(get_session),
    use_cache: bool = Query(True),
):
    return analyze_project_endpoint(request, session, use_cache)


# ===== Export =====
@router.post("/projects/{project_id}/export", response_model=ExportResponse, tags=["Export"])
async def export(project_id: int, request: ExportRequest, session: Session = Depends(get_session)):
    return export_project_context(project_id, request, session)


# ===== Cache =====
@router.post("/invalidate-cache", tags=["Cache"])
async def invalidate(request: InvalidateCacheRequest, session: Session = Depends(get_session)):
    return invalidate_cache(request, session)