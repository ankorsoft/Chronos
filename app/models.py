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
    status: str = Field(default="idle", max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Project settings (stored as JSON string)
    settings_json: str = Field(default="{}", sa_column_kwargs={"comment": "Project settings as JSON"})

    # Ignored patterns (pipe-separated, e.g. "tests|migrations|__pycache__|venv|node_modules")
    ignored_patterns: str = Field(default="tests|migrations|__pycache__|venv|node_modules")

    # Output format preference ('markdown', 'text', 'tree')
    output_format: str = Field(default="markdown")

    # Priority modules for detailed skeleton
    priority_modules: str = Field(default="", sa_column_kwargs={"comment": "Comma-separated list of priority module paths"})

    # Relationships
    snapshots: List["ProjectSnapshot"] = Relationship(back_populates="project")
    exports: List["ProjectExport"] = Relationship(back_populates="project")


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

    # Metadata about what was analyzed (comma-separated file paths for reference)
    files_analyzed: str = Field(default="", sa_column_kwargs={"comment": "Comma-separated list of analyzed file paths"})

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    project: Optional[Project] = Relationship(back_populates="snapshots")


class ProjectExport(SQLModel, table=True):
    """Represents an exported context file for a project."""
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)

    # Export metadata
    format: str = Field()  # 'txt', 'md', 'gpt', 'claude'
    max_tokens: Optional[int] = Field(default=None)
    description: str = Field(default="", sa_column_kwargs={"comment": "Brief export description"})

    # Exported content (structure as text, metrics stored separately)
    content_json: str = Field(sa_column_kwargs={"comment": "Exported context content"})

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    project: Optional[Project] = Relationship(back_populates="exports")