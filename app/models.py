"""
Database models for Chronos Context.
"""
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


class Project(SQLModel, table=True):
    """Represents a Python project being tracked."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    path: str = Field(unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    snapshots: List["ProjectSnapshot"] = Relationship(back_populates="project")


class ProjectSnapshot(SQLModel, table=True):
    """Represents a snapshot of project structure and metrics."""
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    
    # Compressed structure stored as JSON string
    structure_json: str = Field(sa_column_kwargs={"comment": "Compressed project structure"})
    
    # Metrics
    total_files: int = Field(default=0)
    total_lines: int = Field(default=0)
    original_tokens: int = Field(default=0)
    compressed_tokens: int = Field(default=0)
    compression_ratio: float = Field(default=0.0)  # Percentage saved
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    project: Optional[Project] = Relationship(back_populates="snapshots")
