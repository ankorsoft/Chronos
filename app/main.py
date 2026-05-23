"""
FastAPI application for Chronos Context.
"""
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from typing import List
import os

from app.database import engine, create_db_and_tables, get_session
from app.models import Project, ProjectSnapshot
from core.engine import analyze_project

# Create FastAPI app
app = FastAPI(
    title="Chronos Context",
    description="Web service for preparing, storing and serving compressed Python project context for LLM coding",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Initialize database on startup."""
    create_db_and_tables()


# Pydantic models for API
from pydantic import BaseModel

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


class AnalyzeRequest(BaseModel):
    project_path: str


@app.get("/")
async def read_root():
    """Root endpoint with web interface."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chronos Context - LLM Token Optimizer</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px 20px; text-align: center; margin-bottom: 30px; }
        header h1 { font-size: 2.5em; margin-bottom: 10px; }
        header p { opacity: 0.9; font-size: 1.1em; }
        .card { background: white; border-radius: 8px; padding: 25px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .card h2 { color: #667eea; margin-bottom: 15px; font-size: 1.5em; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; font-weight: 600; color: #555; }
        input[type="text"] { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px; }
        input:focus { outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102,126,234,0.1); }
        button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 12px 30px; border-radius: 6px; font-size: 16px; cursor: pointer; transition: transform 0.2s; }
        button:hover { transform: translateY(-2px); }
        button:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 20px; }
        .metric { background: #f8f9fa; padding: 15px; border-radius: 6px; text-align: center; }
        .metric-value { font-size: 2em; font-weight: bold; color: #667eea; }
        .metric-label { color: #666; font-size: 0.9em; margin-top: 5px; }
        .saved { color: #10b981 !important; }
        pre { background: #f8f9fa; padding: 20px; border-radius: 6px; overflow-x: auto; font-family: 'Monaco', 'Consolas', monospace; font-size: 14px; line-height: 1.5; max-height: 500px; overflow-y: auto; }
        .project-list { list-style: none; }
        .project-item { padding: 15px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }
        .project-item:last-child { border-bottom: none; }
        .btn-small { padding: 6px 12px; font-size: 14px; margin-left: 10px; }
        .loading { text-align: center; padding: 40px; color: #666; }
        .hidden { display: none; }
        .success-badge { background: #10b981; color: white; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
    </style>
</head>
<body>
    <header>
        <h1>⏱️ Chronos Context</h1>
        <p>Optimize your Python project context for LLM coding - Save up to 90% on tokens</p>
    </header>
    
    <div class="container">
        <div class="card">
            <h2>📊 Analyze Project</h2>
            <div class="form-group">
                <label for="projectPath">Project Path (absolute)</label>
                <input type="text" id="projectPath" placeholder="/path/to/your/python/project">
            </div>
            <button onclick="analyzeProject()" id="analyzeBtn">Analyze & Compress</button>
            
            <div id="loading" class="loading hidden"><p>⏳ Analyzing project structure...</p></div>
            
            <div id="results" class="hidden">
                <div class="metrics">
                    <div class="metric"><div class="metric-value" id="totalFiles">0</div><div class="metric-label">Total Files</div></div>
                    <div class="metric"><div class="metric-value" id="totalLines">0</div><div class="metric-label">Total Lines</div></div>
                    <div class="metric"><div class="metric-value" id="originalTokens">0</div><div class="metric-label">Original Tokens</div></div>
                    <div class="metric"><div class="metric-value" id="compressedTokens">0</div><div class="metric-label">Compressed Tokens</div></div>
                    <div class="metric"><div class="metric-value saved" id="compressionRatio">0%</div><div class="metric-label">Token Savings</div></div>
                    <div class="metric"><div class="metric-value saved" id="tokensSaved">0</div><div class="metric-label">Tokens Saved</div></div>
                </div>
                <h3 style="margin: 25px 0 15px;">📝 Compressed Context</h3>
                <pre id="structureText"></pre>
                <button onclick="copyContext()" style="margin-top: 15px;">📋 Copy Context</button>
            </div>
        </div>
        
        <div class="card">
            <h2>📁 Recent Projects</h2>
            <ul class="project-list" id="projectList"><li class="loading">Loading projects...</li></ul>
        </div>
    </div>
    
    <script>
        async function analyzeProject() {
            const path = document.getElementById('projectPath').value.trim();
            if (!path) { alert('Please enter a project path'); return; }
            
            const btn = document.getElementById('analyzeBtn');
            const loading = document.getElementById('loading');
            const results = document.getElementById('results');
            
            btn.disabled = true; loading.classList.remove('hidden'); results.classList.add('hidden');
            
            try {
                const response = await fetch('/analyze/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ project_path: path })
                });
                if (!response.ok) { const error = await response.json(); throw new Error(error.detail || 'Analysis failed'); }
                const data = await response.json();
                displayResults(data);
                loadProjects();
            } catch (error) {
                alert('Error: ' + error.message);
            } finally {
                btn.disabled = false; loading.classList.add('hidden');
            }
        }
        
        function displayResults(data) {
            document.getElementById('totalFiles').textContent = data.total_files;
            document.getElementById('totalLines').textContent = data.total_lines;
            document.getElementById('originalTokens').textContent = data.original_tokens.toLocaleString();
            document.getElementById('compressedTokens').textContent = data.compressed_tokens.toLocaleString();
            document.getElementById('compressionRatio').textContent = data.compression_ratio + '%';
            document.getElementById('tokensSaved').textContent = data.tokens_saved.toLocaleString();
            document.getElementById('structureText').textContent = data.structure;
            document.getElementById('results').classList.remove('hidden');
        }
        
        function copyContext() {
            const text = document.getElementById('structureText').textContent;
            navigator.clipboard.writeText(text).then(() => alert('✅ Context copied to clipboard!'));
        }
        
        async function loadProjects() {
            try {
                const response = await fetch('/projects/');
                const projects = await response.json();
                const list = document.getElementById('projectList');
                if (projects.length === 0) { list.innerHTML = '<li class="loading">No projects yet. Analyze one above!</li>'; return; }
                list.innerHTML = projects.map(p => `<li class="project-item"><div><strong>${p.name}</strong><br><small style="color: #666;">${p.path}</small></div><div><span class="success-badge">Active</span><button class="btn-small" onclick="viewSnapshots(${p.id})">View Snapshots</button></div></li>`).join('');
            } catch (error) { console.error('Failed to load projects:', error); }
        }
        
        async function viewSnapshots(projectId) {
            try {
                const response = await fetch('/projects/' + projectId + '/snapshots');
                const snapshots = await response.json();
                if (snapshots.length === 0) { alert('No snapshots for this project'); return; }
                const latest = snapshots[0];
                displayResults(latest);
                document.getElementById('projectPath').value = '';
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } catch (error) { alert('Error loading snapshots: ' + error.message); }
        }
        
        loadProjects();
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@app.post("/projects/", response_model=ProjectResponse)
def create_project(project: ProjectCreate, session: Session = Depends(get_session)):
    """Create a new project to track."""
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


@app.get("/projects/", response_model=List[ProjectResponse])
def list_projects(session: Session = Depends(get_session)):
    """List all tracked projects."""
    projects = session.exec(select(Project)).all()
    return projects


@app.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, session: Session = Depends(get_session)):
    """Get a specific project."""
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.post("/analyze/", response_model=SnapshotResponse)
def analyze_project_endpoint(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """Analyze a Python project and return compressed context with metrics."""
    if not os.path.isdir(request.project_path):
        raise HTTPException(status_code=400, detail=f"Path does not exist: {request.project_path}")
    
    result = analyze_project(request.project_path)
    
    project = session.exec(select(Project).where(Project.path == request.project_path)).first()
    if not project:
        project_name = os.path.basename(request.project_path) or "Unnamed Project"
        project = Project(name=project_name, path=request.project_path)
        session.add(project)
        session.commit()
        session.refresh(project)
    
    snapshot = ProjectSnapshot(
        project_id=project.id,
        structure_json=result["structure"],
        total_files=result["metrics"]["total_files"],
        total_lines=result["metrics"]["total_lines"],
        original_tokens=result["metrics"]["original_tokens"],
        compressed_tokens=result["metrics"]["compressed_tokens"],
        compression_ratio=result["metrics"]["compression_ratio"]
    )
    
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    
    return SnapshotResponse(
        id=snapshot.id,
        project_id=snapshot.project_id,
        structure=snapshot.structure_json,
        total_files=snapshot.total_files,
        total_lines=snapshot.total_lines,
        original_tokens=snapshot.original_tokens,
        compressed_tokens=snapshot.compressed_tokens,
        compression_ratio=snapshot.compression_ratio,
        tokens_saved=result["metrics"]["tokens_saved"],
        created_at=snapshot.created_at.isoformat()
    )


@app.get("/snapshots/{snapshot_id}", response_model=SnapshotResponse)
def get_snapshot(snapshot_id: int, session: Session = Depends(get_session)):
    """Get a specific snapshot by ID."""
    snapshot = session.get(ProjectSnapshot, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    tokens_saved = snapshot.original_tokens - snapshot.compressed_tokens
    
    return SnapshotResponse(
        id=snapshot.id,
        project_id=snapshot.project_id,
        structure=snapshot.structure_json,
        total_files=snapshot.total_files,
        total_lines=snapshot.total_lines,
        original_tokens=snapshot.original_tokens,
        compressed_tokens=snapshot.compressed_tokens,
        compression_ratio=snapshot.compression_ratio,
        tokens_saved=tokens_saved,
        created_at=snapshot.created_at.isoformat()
    )


@app.get("/projects/{project_id}/snapshots", response_model=List[SnapshotResponse])
def list_project_snapshots(project_id: int, session: Session = Depends(get_session)):
    """List all snapshots for a project."""
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    snapshots = session.exec(
        select(ProjectSnapshot)
        .where(ProjectSnapshot.project_id == project_id)
        .order_by(ProjectSnapshot.created_at.desc())
    ).all()
    
    return [
        SnapshotResponse(
            id=s.id,
            project_id=s.project_id,
            structure=s.structure_json,
            total_files=s.total_files,
            total_lines=s.total_lines,
            original_tokens=s.original_tokens,
            compressed_tokens=s.compressed_tokens,
            compression_ratio=s.compression_ratio,
            tokens_saved=s.original_tokens - s.compressed_tokens,
            created_at=s.created_at.isoformat()
        )
        for s in snapshots
    ]
