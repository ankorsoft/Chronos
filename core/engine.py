"""
Core engine for parsing and compressing Python project structure.
Isolated module without framework dependencies.
"""
import ast
import os
from pathlib import Path
from typing import Dict, List, Any
import tiktoken


class PythonParser:
    """Parse Python files to extract structure (classes, functions, imports)."""
    
    @staticmethod
    def parse_file(file_path: str) -> Dict[str, Any]:
        """Parse a single Python file and return its structure."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source, filename=file_path)
            
            structure = {
                "file": file_path,
                "imports": [],
                "classes": [],
                "functions": [],
                "lines": len(source.splitlines())
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        structure["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        structure["imports"].append(f"{module}.{alias.name}")
                elif isinstance(node, ast.ClassDef):
                    structure["classes"].append({
                        "name": node.name,
                        "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
                        "line": node.lineno
                    })
                elif isinstance(node, ast.FunctionDef):
                    # Check if it's a top-level function
                    is_method = False
                    for parent in ast.walk(tree):
                        if isinstance(parent, ast.ClassDef):
                            if node in parent.body:
                                is_method = True
                                break
                    
                    if not is_method:
                        structure["functions"].append({
                            "name": node.name,
                            "line": node.lineno
                        })
            
            return structure
            
        except Exception as e:
            return {"file": file_path, "error": str(e), "lines": 0}


class ProjectCompressor:
    """Compress project structure into LLM-friendly context."""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.parser = PythonParser()
    
    def scan_project(self) -> List[Dict[str, Any]]:
        """Scan all Python files in the project."""
        structures = []
        
        for py_file in self.project_path.rglob("*.py"):
            # Skip common non-essential directories
            if any(part.startswith('.') for part in py_file.parts):
                continue
            if 'venv' in py_file.parts or '__pycache__' in py_file.parts:
                continue
            
            structure = self.parser.parse_file(str(py_file))
            structures.append(structure)
        
        return structures
    
    def compress_structure(self, structures: List[Dict[str, Any]]) -> str:
        """Convert parsed structures into compressed text format."""
        lines = []
        lines.append("# Project Structure Overview")
        lines.append("")
        
        for struct in structures:
            if "error" in struct:
                continue
            
            rel_path = os.path.relpath(struct["file"], self.project_path)
            lines.append(f"## {rel_path}")
            lines.append(f"Lines: {struct['lines']}")
            
            if struct.get("imports"):
                lines.append(f"Imports: {', '.join(struct['imports'][:10])}")
                if len(struct["imports"]) > 10:
                    lines.append(f"  ... and {len(struct['imports']) - 10} more")
            
            if struct.get("classes"):
                for cls in struct["classes"]:
                    methods_str = ", ".join(cls["methods"][:5])
                    lines.append(f"  Class {cls['name']} (line {cls['line']}): [{methods_str}]")
                    if len(cls["methods"]) > 5:
                        lines.append(f"    ... and {len(cls['methods']) - 5} more methods")
            
            if struct.get("functions"):
                for func in struct["functions"]:
                    lines.append(f"  Function {func['name']} (line {func['line']})")
            
            lines.append("")
        
        return "\n".join(lines)


class TokenCounter:
    """Count tokens using tiktoken."""
    
    def __init__(self, encoding_name: str = "cl100k_base"):
        self.encoding = tiktoken.get_encoding(encoding_name)
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))
    
    def count_tokens_in_files(self, project_path: str) -> int:
        """Count total tokens in all Python files."""
        total = 0
        path = Path(project_path)
        
        for py_file in path.rglob("*.py"):
            if any(part.startswith('.') for part in py_file.parts):
                continue
            if 'venv' in py_file.parts or '__pycache__' in py_file.parts:
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                total += self.count_tokens(content)
            except:
                pass
        
        return total


def analyze_project(project_path: str) -> Dict[str, Any]:
    """
    Main entry point: analyze a project and return compressed context with metrics.
    """
    compressor = ProjectCompressor(project_path)
    token_counter = TokenCounter()
    
    # Scan and parse
    structures = compressor.scan_project()
    
    # Compress
    compressed_text = compressor.compress_structure(structures)
    
    # Count tokens
    original_tokens = token_counter.count_tokens_in_files(project_path)
    compressed_tokens = token_counter.count_tokens(compressed_text)
    
    # Calculate metrics
    total_files = len([s for s in structures if "error" not in s])
    total_lines = sum(s.get("lines", 0) for s in structures)
    compression_ratio = ((original_tokens - compressed_tokens) / original_tokens * 100) if original_tokens > 0 else 0
    
    return {
        "structure": compressed_text,
        "metrics": {
            "total_files": total_files,
            "total_lines": total_lines,
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "compression_ratio": round(compression_ratio, 2),
            "tokens_saved": original_tokens - compressed_tokens
        }
    }
