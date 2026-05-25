"""
SAGE-PRO LSP Bridge — Semantic Codebase Awareness
═══════════════════════════════════════════════════
Feature 4: Gives agents native Language Server Protocol capabilities.

Instead of just reading files, agents can execute:
  - Find All References
  - Go to Definition
  - Rename Symbol
  - Get Diagnostics
  - Code Completions (for validation)

This enables the agents to perform surgical, large-scale refactors
across 10,000+ file repositories without hallucinating imports.

Architecture:
  Agent requests LSP operation → LSP Bridge → pylsp/jedi subprocess
  → Structured results → Injected into agent context
"""

import asyncio
import json
import os
import structlog
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = structlog.get_logger(__name__)


class LSPBridge:
    """Provides Language Server Protocol operations for SAGE agents."""

    def __init__(self, project_root: str = ".") -> None:
        """Initializes the LSP Bridge.

        Args:
            project_root: Root directory of the project being analyzed.
        """
        self.project_root = Path(project_root).resolve()
        logger.info("lsp_bridge_initialized", root=str(self.project_root))

    async def find_references(
        self, symbol: str, file_path: str, line: int, column: int
    ) -> List[Dict[str, Any]]:
        """Finds all references to a symbol across the project.

        Args:
            symbol: The symbol name to search for.
            file_path: File where the symbol is defined/used.
            line: Line number (0-indexed).
            column: Column number (0-indexed).

        Returns:
            List of reference locations with file, line, column.
        """
        # Use jedi for Python analysis
        try:
            import jedi
            script = jedi.Script(
                path=str(self.project_root / file_path),
                project=jedi.Project(path=str(self.project_root)),
            )
            refs = script.get_references(line=line + 1, column=column)
            results = []
            for ref in refs:
                results.append({
                    "file": str(ref.module_path) if ref.module_path else file_path,
                    "line": ref.line - 1,
                    "column": ref.column,
                    "name": ref.name,
                    "type": ref.type,
                    "full_name": ref.full_name or "",
                    "description": ref.description,
                })
            logger.info("lsp_find_references", symbol=symbol, count=len(results))
            return results
        except Exception as e:
            logger.error("lsp_find_references_failed", error=str(e))
            return await self._fallback_grep(symbol)

    async def goto_definition(
        self, file_path: str, line: int, column: int
    ) -> List[Dict[str, Any]]:
        """Finds the definition of a symbol.

        Args:
            file_path: File where the symbol is referenced.
            line: Line number (0-indexed).
            column: Column number (0-indexed).

        Returns:
            List of definition locations.
        """
        try:
            import jedi
            script = jedi.Script(
                path=str(self.project_root / file_path),
                project=jedi.Project(path=str(self.project_root)),
            )
            defs = script.goto(line=line + 1, column=column)
            results = []
            for d in defs:
                results.append({
                    "file": str(d.module_path) if d.module_path else file_path,
                    "line": d.line - 1 if d.line else 0,
                    "column": d.column,
                    "name": d.name,
                    "type": d.type,
                    "full_name": d.full_name or "",
                    "description": d.description,
                })
            logger.info("lsp_goto_definition", count=len(results))
            return results
        except Exception as e:
            logger.error("lsp_goto_definition_failed", error=str(e))
            return []

    async def get_diagnostics(self, file_path: str) -> List[Dict[str, Any]]:
        """Gets diagnostics (errors, warnings) for a file.

        Uses both Jedi and Ruff for comprehensive analysis.

        Args:
            file_path: Path to the file to analyze.

        Returns:
            List of diagnostic entries.
        """
        diagnostics: List[Dict[str, Any]] = []
        full_path = str(self.project_root / file_path)

        # Jedi diagnostics
        try:
            import jedi
            script = jedi.Script(path=full_path)
            for err in script.get_names(all_scopes=True):
                if err.type == "statement" and not err.defined_names():
                    diagnostics.append({
                        "source": "jedi",
                        "severity": "warning",
                        "message": f"Potential issue with: {err.name}",
                        "line": err.line - 1,
                        "column": err.column,
                    })
        except Exception as e:
            logger.warning("jedi_diagnostics_failed", error=str(e))

        # Ruff diagnostics (fast)
        try:
            proc = await asyncio.create_subprocess_exec(
                "ruff", "check", "--output-format=json", full_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if stdout:
                for issue in json.loads(stdout.decode("utf-8", errors="ignore")):
                    diagnostics.append({
                        "source": "ruff",
                        "severity": "warning",
                        "message": issue.get("message", ""),
                        "line": issue.get("location", {}).get("row", 0) - 1,
                        "column": issue.get("location", {}).get("column", 0),
                        "code": issue.get("code", ""),
                    })
        except Exception as e:
            logger.warning("ruff_diagnostics_failed", error=str(e))

        logger.info("lsp_diagnostics", file=file_path, count=len(diagnostics))
        return diagnostics

    async def rename_symbol(
        self, file_path: str, line: int, column: int, new_name: str
    ) -> Dict[str, Any]:
        """Computes a rename refactoring for a symbol.

        Args:
            file_path: File containing the symbol.
            line: Line number (0-indexed).
            column: Column number (0-indexed).
            new_name: The new name for the symbol.

        Returns:
            Dict with 'changes' mapping filenames to list of edits.
        """
        try:
            import jedi
            script = jedi.Script(
                path=str(self.project_root / file_path),
                project=jedi.Project(path=str(self.project_root)),
            )
            refactoring = script.rename(line=line + 1, column=column, new_name=new_name)
            changes: Dict[str, List[Dict[str, Any]]] = {}

            for fp, edits in refactoring.get_changed_files().items():
                rel_path = str(Path(fp).relative_to(self.project_root))
                changes[rel_path] = [{
                    "new_content": edits,
                }]

            logger.info("lsp_rename", new_name=new_name, files_changed=len(changes))
            return {"changes": changes, "new_name": new_name}
        except Exception as e:
            logger.error("lsp_rename_failed", error=str(e))
            return {"changes": {}, "error": str(e)}

    async def get_project_symbols(self, max_depth: int = 3) -> List[Dict[str, Any]]:
        """Scans the project for all top-level symbols (classes, functions).

        Args:
            max_depth: Max directory depth to scan.

        Returns:
            List of symbol descriptors.
        """
        symbols: List[Dict[str, Any]] = []

        for py_file in self.project_root.rglob("*.py"):
            # Skip hidden dirs and common excludes
            parts = py_file.relative_to(self.project_root).parts
            if any(p.startswith('.') or p in ('__pycache__', 'node_modules', 'venv') for p in parts):
                continue
            if len(parts) > max_depth:
                continue

            try:
                import jedi
                script = jedi.Script(path=str(py_file))
                names = script.get_names(all_scopes=False)
                for name in names:
                    if name.type in ('class', 'function'):
                        symbols.append({
                            "name": name.name,
                            "type": name.type,
                            "file": str(py_file.relative_to(self.project_root)),
                            "line": name.line - 1,
                            "description": name.description,
                        })
            except Exception:
                continue

        logger.info("project_symbols_scanned", count=len(symbols))
        return symbols

    async def _fallback_grep(self, pattern: str) -> List[Dict[str, Any]]:
        """Fallback: uses grep when Jedi is unavailable.

        Args:
            pattern: The search pattern.

        Returns:
            List of match locations.
        """
        results: List[Dict[str, Any]] = []
        try:
            proc = await asyncio.create_subprocess_exec(
                "grep", "-rn", "--include=*.py", pattern, str(self.project_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if stdout:
                for line in stdout.decode("utf-8", errors="ignore").splitlines()[:50]:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        results.append({
                            "file": parts[0],
                            "line": int(parts[1]) - 1,
                            "content": parts[2].strip(),
                        })
        except Exception as e:
            logger.warning("grep_fallback_failed", error=str(e))

        return results
