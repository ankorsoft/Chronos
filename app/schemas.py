"""
Pydantic schemas for Chronos Context API.
"""
from typing import Optional
from pydantic import BaseModel


# ===== Project Schemas =====

class ProjectCreate(BaseModel):
    name: str
    path: str


class ProjectResponse(BaseModel):
    id: int
    name: str
    path: str
    created_at: str

    class Config:
        from_attributes = True


# ===== Snapshot Schemas =====

class SnapshotResponse(BaseModel):
    id: int
    project_id: int
    structure: str
    total_files: int
    total_lines: int
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    tokens_saved: int
    created_at: str

    class Config:
        from_attributes = True


# ===== Request/Response Schemas =====

class AnalyzeRequest(BaseModel):
    project_path: str


class InvalidateCacheRequest(BaseModel):
    project_id: int


class ContextResponse(BaseModel):
    structure: str
    metrics: dict

    class Config:
        from_attributes = True


# ===== Project Settings =====

class ProjectSettingsUpdate(BaseModel):
    ignored_patterns: Optional[str] = None
    output_format: Optional[str] = None
    priority_modules: Optional[str] = None


class ProjectSettingsResponse(BaseModel):
    project_id: int
    ignored_patterns: str
    output_format: str
    priority_modules: str

    class Config:
        from_attributes = True


# ===== Export Schemas =====

class ExportRequest(BaseModel):
    format: str = "txt"
    max_tokens: Optional[int] = None
    include_imports: bool = True
    include_classes: bool = True
    include_functions: bool = True
    depth: int = 1


class ExportResponse(BaseModel):
    content: str
    format: str
    tokens_counted: int

    class Config:
        from_attributes = True