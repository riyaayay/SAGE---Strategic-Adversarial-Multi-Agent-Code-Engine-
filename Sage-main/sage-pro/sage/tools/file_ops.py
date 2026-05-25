"""
SAGE-PRO Tool: File Operations
════════════════════════════════
file_read, file_write, and repo_scan implementations.

Config (env vars):
    TOOL_FILE_MAX_SIZE      — max bytes to read per file (default: 12000)
    TOOL_FILE_MAX_FILES     — max files per glob (default: 10)
    TOOL_REPO_SCAN_EXCLUDE  — comma-separated dirs to exclude
"""

import os
import glob as glob_module
import structlog
from typing import Dict, Any, Optional, List

logger = structlog.get_logger(__name__)

MAX_FILE_SIZE = int(os.environ.get("TOOL_FILE_MAX_SIZE", "12000"))
MAX_FILES_PER_GLOB = int(os.environ.get("TOOL_FILE_MAX_FILES", "10"))
REPO_SCAN_EXCLUDE = set(
    os.environ.get(
        "TOOL_REPO_SCAN_EXCLUDE",
        ".git,__pycache__,node_modules,.venv,venv,.tox,.mypy_cache,.pytest_cache"
    ).split(",")
)


async def tool_file_read(
    path: str,
    reason: str,
    extract: str,
    project_root: str = ".",
) -> Dict[str, Any]:
    """Reads files from the workspace.

    Args:
        path: File path or glob pattern relative to project root.
        reason: What the caller needs from this file.
        extract: What to extract (full_content, imports_only, etc.).
        project_root: Root directory for relative paths.

    Returns:
        Dict with 'files' mapping, 'extract', and 'reason'.
    """
    full_path = os.path.join(project_root, path) if not os.path.isabs(path) else path

    if "*" in full_path:
        files = glob_module.glob(full_path, recursive=True)
    else:
        files = [full_path]

    files = files[:MAX_FILES_PER_GLOB]
    results = {}

    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                content = fh.read()

            # Apply extraction filter
            if extract == "imports_only":
                lines = content.split("\n")
                content = "\n".join(
                    l for l in lines
                    if l.strip().startswith(("import ", "from ", "require(", "const ", "export "))
                )
            elif extract == "exports_only":
                lines = content.split("\n")
                content = "\n".join(
                    l for l in lines
                    if l.strip().startswith(("export ", "module.exports", "def ", "class ", "async def "))
                )
            elif extract == "type_definitions":
                lines = content.split("\n")
                content = "\n".join(
                    l for l in lines
                    if any(kw in l for kw in ("class ", "TypedDict", "BaseModel", "interface ", "type ", "Protocol"))
                )
            elif extract == "config_values":
                lines = content.split("\n")
                content = "\n".join(
                    l for l in lines
                    if "=" in l and not l.strip().startswith("#")
                )

            # Truncate if too large
            if len(content) > MAX_FILE_SIZE:
                content = content[:MAX_FILE_SIZE] + "\n... [TRUNCATED]"

            results[f] = content

        except Exception as e:
            results[f] = f"ERROR: {e}"

    logger.info("file_read_complete", files_read=len(results), extract=extract)
    return {"files": results, "extract": extract, "reason": reason}


async def tool_file_write(
    path: str,
    content: str,
    mode: str = "overwrite",
    project_root: str = ".",
) -> Dict[str, Any]:
    """Writes or appends to a file.

    Args:
        path: File path relative to project root.
        content: Content to write.
        mode: 'create', 'overwrite', or 'append'.
        project_root: Root directory for relative paths.

    Returns:
        Dict with 'path', 'status', and 'bytes'.
    """
    full_path = os.path.join(project_root, path) if not os.path.isabs(path) else path

    # Safety: don't write outside project root
    real_root = os.path.realpath(project_root)
    real_path = os.path.realpath(full_path)
    if not real_path.startswith(real_root):
        return {"path": path, "status": "error", "error": "Path escapes project root"}

    # Create directories
    parent = os.path.dirname(full_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    # Check if file exists for 'create' mode
    if mode == "create" and os.path.exists(full_path):
        return {"path": path, "status": "error", "error": "File already exists"}

    write_mode = "a" if mode == "append" else "w"

    with open(full_path, write_mode, encoding="utf-8") as f:
        f.write(content)

    byte_count = len(content.encode("utf-8"))
    logger.info("file_write_complete", path=path, mode=mode, bytes=byte_count)
    return {"path": path, "status": "written", "bytes": byte_count}


async def tool_repo_scan(
    root: str = ".",
    depth: int = 3,
    filter_pattern: Optional[str] = None,
) -> Dict[str, Any]:
    """Scans a directory tree to understand project structure.

    Args:
        root: Directory to scan from.
        depth: How many levels deep to scan.
        filter_pattern: Optional glob suffix to filter files.

    Returns:
        Dict with 'tree' mapping dirs to file lists, 'root', and 'depth'.
    """
    tree: Dict[str, List[str]] = {}

    for dirpath, dirnames, filenames in os.walk(root):
        # Calculate depth
        rel = os.path.relpath(dirpath, root)
        level = 0 if rel == "." else rel.count(os.sep) + 1

        if level >= depth:
            dirnames.clear()
            continue

        # Filter excluded directories
        dirnames[:] = [d for d in dirnames if d not in REPO_SCAN_EXCLUDE]

        # Filter files by pattern if provided
        if filter_pattern:
            suffix = filter_pattern.lstrip("*")
            files = [f for f in filenames if f.endswith(suffix)]
        else:
            files = filenames

        if files:
            tree[os.path.relpath(dirpath, root)] = files

    logger.info("repo_scan_complete", root=root, depth=depth, dirs=len(tree))
    return {"tree": tree, "root": root, "depth": depth}
