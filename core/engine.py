"""
Core engine for parsing and compressing Python project structure.
Isolated module without framework dependencies.
"""
import ast
import os
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple, Optional, FrozenSet
import tiktoken

from core.cache import AnalysisCache, FileHashCache


class PythonParser:
    """Parse Python files to extract structure (classes, functions, imports, docstrings, inheritance)."""
    
    @staticmethod
    def _extract_docstring(node: ast.AST) -> str:
        """Extract the first docstring from an AST node."""
        if node.body and isinstance(node.body[0], ast.Expr):
            val = node.body[0].value
            if isinstance(val, (ast.Str, ast.Constant)):
                doc = val.s if hasattr(val, 's') else getattr(val, 'value', '')
                return doc if isinstance(doc, str) else ""
        return ""
    
    @staticmethod
    def _extract_bases(node: ast.ClassDef) -> List[str]:
        """Extract base class names from a ClassDef node."""
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                parts = []
                n: Optional[ast.AST] = base
                while n is not None:
                    if isinstance(n, ast.Name):
                        parts.append(n.id)
                        n = None
                    elif isinstance(n, ast.Attribute):
                        parts.append(n.attr)
                        n = n.value
                    else:
                        n = None
                bases.append(".".join(reversed(parts)))
        return bases
    
    @staticmethod
    def _extract_args(func_node: ast.FunctionDef) -> Dict[str, Any]:
        """Extract function arguments info."""
        args_info = {"params": [], "args_type": None, "kwargs_type": None}
        
        args = func_node.args
        for arg in args.args:
            param = {"name": arg.arg}
            if hasattr(arg, 'annotation') and arg.annotation:
                if isinstance(arg.annotation, ast.Name):
                    param["type"] = arg.annotation.id
                elif isinstance(arg.annotation, ast.Constant):
                    param["type"] = str(arg.annotation.value)
            args_info["params"].append(param)
        
        if args.vararg:
            args_info["args_type"] = args.vararg.arg
        if args.kwarg:
            args_info["kwargs_type"] = args.kwarg.arg
        
        for default in args.defaults:
            if isinstance(default, ast.Constant):
                pass  # skip defaults for now
        
        if hasattr(func_node.returns, 'id') and func_node.returns:
            args_info["returns"] = func_node.returns.id
        
        return args_info
    
    @staticmethod
    def parse_file(file_path: str) -> Dict[str, Any]:
        """Parse a single Python file and return its structure."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source, filename=file_path)
            
            # Check if file is __init__.py (package marker)
            is_package = os.path.basename(file_path) == "__init__.py"
            
            structure = {
                "file": file_path,
                "is_package": is_package,
                "imports": [],
                "classes": [],
                "functions": [],
                "module_docstring": "",
                "lines": len(source.splitlines()),
                "complexity_score": 0  # Will be calculated later
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
                    docstring = PythonParser._extract_docstring(node)
                    bases = PythonParser._extract_bases(node)
                    methods = []
                    for method in node.body:
                        if isinstance(method, ast.FunctionDef):
                            method_info = {
                                "name": method.name,
                                "line": method.lineno,
                                "args": PythonParser._extract_args(method),
                                "docstring": PythonParser._extract_docstring(method)[:100]  # truncate long docstrings
                            }
                            methods.append(method_info)
                    
                    structure["classes"].append({
                        "name": node.name,
                        "bases": bases,
                        "methods": methods,
                        "line": node.lineno,
                        "docstring": docstring[:200],  # truncate long docstrings
                        "public_methods": [m["name"] for m in methods if not m["name"].startswith("_")],
                        "private_methods": [m["name"] for m in methods if m["name"].startswith("_") and not m["name"].startswith("__")]
                    })
                elif isinstance(node, ast.FunctionDef):
                    # Check if it's a top-level function (not inside a class)
                    is_method = False
                    for parent_node in ast.iter_child_nodes(tree):
                        if isinstance(parent_node, ast.ClassDef) and node in parent_node.body:
                            is_method = True
                            break
                    
                    if not is_method:
                        args_info = PythonParser._extract_args(node)
                        docstring = PythonParser._extract_docstring(node)
                        structure["functions"].append({
                            "name": node.name,
                            "line": node.lineno,
                            "args": args_info,
                            "docstring": docstring[:200],
                            "is_public": not node.name.startswith("_")
                        })
            
            # Calculate simple complexity score (number of control flow statements)
            complexity = 0
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.ExceptHandler)):
                    complexity += 1
            structure["complexity_score"] = complexity
            
            return structure
            
        except Exception as e:
            return {"file": file_path, "error": str(e), "lines": 0, "is_package": False}


class ProjectCompressor:
    """Compress project structure into LLM-friendly context."""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.parser = PythonParser()
    
    def scan_project(self) -> List[Dict[str, Any]]:
        """Scan all Python files in the project.
        
        Returns list of file structures sorted by package depth.
        """
        structures = []
        
        for py_file in self.project_path.rglob("*.py"):
            # Skip common non-essential directories
            if any(part.startswith('.') for part in py_file.parts):
                continue
            if 'venv' in py_file.parts or '__pycache__' in py_file.parts:
                continue
            
            structure = self.parser.parse_file(str(py_file))
            structures.append(structure)
        
        # Sort by package depth (packages first, then by path)
        structures.sort(key=lambda s: (s.get("is_package", False), os.path.relpath(s["file"], self.project_path)))
        
        return structures
    
    def build_tree_structure(self, structures: List[Dict[str, Any]]) -> str:
        """Build a tree-like package structure visualization."""
        # Build directory tree
        dirs = {}
        for struct in structures:
            if "error" in struct:
                continue
            rel_path = os.path.relpath(struct["file"], self.project_path)
            parts = Path(rel_path).parts
            
            # Track directory hierarchy
            current = ""
            for part in parts[:-1]:
                current = os.path.join(current, part) if current else part
                dirs.setdefault(current, {"is_package": False, "children": []})
                if struct.get("is_package"):
                    dirs[current]["is_package"] = True
            
            # Add file to its directory
            file_dir = os.path.join(*parts[:-1]) if len(parts) > 1 else "."
            dirs[file_dir] = dirs.get(file_dir, {"is_package": False, "children": []})
            dirs[file_dir]["children"].append({
                "name": parts[-1],
                "is_package": struct.get("is_package", False),
                "classes": len(struct.get("classes", [])),
                "functions": len(struct.get("functions", [])),
                "lines": struct.get("lines", 0)
            })
        
        # Render tree recursively
        def render_tree(prefix: str, dir_data: dict, is_last: bool = True) -> List[str]:
            lines = []
            connector = "└── " if is_last else "├── "
            
            if dir_data.get("is_package"):
                lines.append(f"{prefix}{connector}📦 {prefix.split('└')[-1].strip() or '.'}/")
            elif dir_data["children"]:
                lines.append(f"{prefix}{connector}📄 {'/'.join(k for k in dir_data['children'][:3])}")
                if len(dir_data["children"]) > 3:
                    lines.append(f"{prefix}    ... +{len(dir_data['children']) - 3} more files")
            
            # Render children
            child_prefix = prefix + ("    " if is_last else "│   ")
            children = dir_data.get("children", [])
            for i, child in enumerate(children[:20]):  # limit to 20 children
                is_last_child = (i == len(children) - 1)
                lines.append(f"{child_prefix}{connector[:-1]} {'📦' if child['is_package'] else '🐍'} {child['name']}")
            
            return lines
        
        tree_lines = ["├── 📦 project/"]
        for i, (dir_name, dir_data) in enumerate(list(dirs.items())[:15]):  # limit top-level
            is_last = (i == len(dirs) - 1)
            prefix = "    " if is_last else "│   "
            tree_lines.extend(render_tree(prefix, dir_data, is_last))
        
        return "\n".join(tree_lines)
    
    def compress_structure(self, structures: List[Dict[str, Any]], format_type: str = "markdown") -> str:
        """Convert parsed structures into compressed text format.
        
        Args:
            structures: List of parsed file structures
            format_type: Output format ('markdown' or 'text')
        """
        if format_type == "markdown":
            return self._compress_markdown(structures)
        return self._compress_text(structures)
    
    def _compress_text(self, structures: List[Dict[str, Any]]) -> str:
        """Original text format (preserved for compatibility)."""
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
                    methods_str = ", ".join(cls.get("methods", [])[:5])
                    lines.append(f"  Class {cls['name']} (line {cls['line']}): [{methods_str}]")
                    if len(cls.get("methods", [])) > 5:
                        lines.append(f"    ... and {len(cls['methods']) - 5} more methods")
            
            if struct.get("functions"):
                for func in struct["functions"]:
                    lines.append(f"  Function {func['name']} (line {func['line']})")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _compress_markdown(self, structures: List[Dict[str, Any]]) -> str:
        """Markdown format with tree structure and detailed info."""
        lines = []
        
        # Package tree
        lines.append("# Project Structure Overview")
        lines.append("")
        lines.append("## 📂 Package Tree")
        lines.append(self.build_tree_structure(structures))
        lines.append("")
        
        # File details grouped by module
        lines.append("## 📄 Module Details")
        lines.append("")
        
        for struct in structures:
            if "error" in struct:
                continue
            
            rel_path = os.path.relpath(struct["file"], self.project_path)
            prefix = "📦" if struct.get("is_package") else "🐍"
            
            lines.append(f"### {prefix} `{rel_path}`")
            lines.append("")
            lines.append(f"**{struct['lines']}** lines | **Complexity:** {struct.get('complexity_score', 0)}")
            
            # Module docstring
            if struct.get("module_docstring"):
                lines.append("")
                lines.append(f"> {struct['module_docstring'][:150]}")
            
            # Imports section (grouped)
            if struct.get("imports"):
                unique_imports = list(dict.fromkeys(struct["imports"]))  # deduplicate preserving order
                lines.append("")
                lines.append("**Imports:**")
                lines.append("")
                for imp in unique_imports[:15]:
                    icon = "📦" if "." in imp and not imp.startswith(".") else "📥"
                    lines.append(f"- {icon} `{imp}`")
                if len(unique_imports) > 15:
                    lines.append(f"- _... and {len(unique_imports) - 15} more_")
            
            # Classes section
            classes = struct.get("classes", [])
            if classes:
                lines.append("")
                lines.append("**Classes:**")
                lines.append("")
                
                for cls in classes:
                    bases_str = f"({', '.join(cls.get('bases', []))})" if cls.get('bases') else ""
                    visibility = "🟢" if cls.get('public_methods') else "🔵"
                    lines.append(f"#### {visibility} `class {cls['name']}` {bases_str}")
                    lines.append("")
                    
                    if cls.get("docstring"):
                        lines.append(f"> {cls['docstring'][:150]}")
                        lines.append("")
                    
                    # Public methods
                    public_methods = [m for m in cls.get("methods", []) if not m["name"].startswith("_")]
                    private_methods = [m for m in cls.get("methods", []) if m["name"].startswith("_") and not m["name"].startswith("__")]
                    
                    if public_methods:
                        lines.append("**Public methods:**")
                        for m in public_methods[:8]:
                            args_str = ", ".join(p["name"] + (f": `{p.get('type', '')}`" if p.get("type") else p["name"]) for p in m.get("args", {}).get("params", [])[:5])
                            ret = f" -> `{m.get('args', {}).get('returns', '')}`" if m.get("args", {}).get("returns") else ""
                            lines.append(f"- `def {m['name']}({args_str}){ret}`")
                        if len(public_methods) > 8:
                            lines.append(f"- _... and {len(public_methods) - 8} more_")
                    
                    # Private methods (collapsed)
                    if private_methods:
                        lines.append("")
                        lines.append(f"*{len(private_methods)} private methods (click to expand)*")
            
            # Top-level functions
            functions = struct.get("functions", [])
            if functions:
                public_funcs = [f for f in functions if f.get("is_public", True)]
                if public_funcs:
                    lines.append("")
                    lines.append("**Functions:**")
                    lines.append("")
                    for func in public_funcs[:10]:
                        args_str = ", ".join(p["name"] + (f": `{p.get('type', '')}`" if p.get("type") else p["name"]) for p in func.get("args", {}).get("params", [])[:5])
                        ret = f" -> `{func.get('args', {}).get('returns', '')}`" if func.get("args", {}).get("returns") else ""
                        icon = "🟢" if func.get("is_public") else "🔵"
                        lines.append(f"- {icon} `def {func['name']}({args_str}){ret}`")
                    if len(public_funcs) > 10:
                        lines.append(f"- _... and {len(public_funcs) - 10} more_")
            
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


def analyze_project(project_path: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Main entry point: analyze a project and return compressed context with metrics.
    
    Supports incremental updates via file hash caching.
    
    Args:
        project_path: Path to the Python project
        use_cache: Whether to use cached results when possible
    
    Returns:
        Dictionary with 'structure' (compressed text) and 'metrics' (dict).
        Also includes 'cache_info' if caching was used.
    """
    compressor = ProjectCompressor(project_path)
    token_counter = TokenCounter()
    cache = AnalysisCache(project_path)
    
    result = {}
    
    # Try cached result first
    if use_cache and cache.is_valid():
        current_hashes = FileHashCache(project_path).compute_directory_hashes()
        needs_update, changed = cache.needs_update(current_hashes)
        
        if not needs_update:
            cached_result = cache.get_cached_result()
            if cached_result:
                cached_result["cache_hit"] = True
                cached_result["changed_files"] = list(changed) if changed else []
                return cached_result
    
    # Full analysis (or incremental for large projects)
    structures = compressor.scan_project()
    compressed_text = compressor.compress_structure(structures, format_type="markdown")
    
    # Count tokens
    original_tokens = token_counter.count_tokens_in_files(project_path)
    compressed_tokens = token_counter.count_tokens(compressed_text)
    
    # Calculate metrics
    total_files = len([s for s in structures if "error" not in s])
    total_lines = sum(s.get("lines", 0) for s in structures)
    compression_ratio = ((original_tokens - compressed_tokens) / original_tokens * 100) if original_tokens > 0 else 0
    
    metrics = {
        "total_files": total_files,
        "total_lines": total_lines,
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "compression_ratio": round(compression_ratio, 2),
        "tokens_saved": original_tokens - compressed_tokens
    }
    
    # Update cache
    current_hashes = FileHashCache(project_path).compute_directory_hashes()
    cache.save_result({"structure": compressed_text, "metrics": metrics})
    cache.save_hashes(current_hashes)
    
    result = {
        "structure": compressed_text,
        "metrics": metrics,
        "cache_hit": False,
        "changed_files": []  # Full analysis → nothing changed
    }
    
    return result


def analyze_incremental(project_path: str, base_structures: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Set[str]]:
    """
    Incrementally update structures for changed files only.
    
    Args:
        project_path: Path to the project
        base_structures: Previous full structures list
    
    Returns:
        Tuple of (updated structures, set of changed file paths)
    """
    compressor = ProjectCompressor(project_path)
    
    # Get current hashes and compare
    file_cache = FileHashCache(project_path)
    current_hashes = file_cache.compute_directory_hashes()
    
    # Build a map of existing structures by relative path
    struct_map = {}
    for s in base_structures:
        rel = os.path.relpath(s["file"], project_path)
        struct_map[rel] = s
    
    # Re-parse only changed/new files
    changed_files = set()
    updated_map = dict(struct_map)  # copy
    
    for rel_path, current_hash in current_hashes.items():
        full_path = os.path.join(project_path, rel_path)
        old_hash = FileHashCache(project_path).compute_file_hash(full_path)
        
        if rel_path not in struct_map or current_hash != old_hash:
            new_struct = compressor.parser.parse_file(full_path)
            updated_map[rel_path] = new_struct
            changed_files.add(rel_path)
    
    # Remove deleted files
    for rel_path in list(updated_map.keys()):
        if rel_path not in current_hashes:
            del updated_map[rel_path]
            changed_files.add(f"-{rel_path}")  # mark as deleted
    
    return list(updated_map.values()), changed_files
