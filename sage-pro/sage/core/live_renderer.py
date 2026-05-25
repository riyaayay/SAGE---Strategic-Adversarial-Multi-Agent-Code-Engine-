"""
SAGE-PRO Live Rendering Engine — "Glass"
══════════════════════════════════════════
Feature 1: Interactive sandbox that renders agent-generated code
in real-time within the IDE's side-panel.

Supports:
  - HTML/CSS/JS (direct iframe injection)
  - Python scripts (via Pyodide WASM runtime)
  - React/Vue apps (via ESM CDN transpilation)
  - Data visualizations (Matplotlib/Plotly → SVG/HTML export)

Architecture:
  Agent produces code → Glass extracts renderable artifacts →
  Serves them on an ephemeral HTTP endpoint → Frontend iframe loads it.

Security:
  All rendered code runs in a sandboxed iframe with:
    sandbox="allow-scripts allow-same-origin"
  No filesystem access, no network access beyond CDN imports.
"""

import asyncio
import hashlib
import html
import os
import re
import shutil
import structlog
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

logger = structlog.get_logger(__name__)

# In-memory store for rendered previews (hash → content)
_preview_store: Dict[str, Dict[str, Any]] = {}

# Max previews to keep in memory (LRU eviction)
MAX_PREVIEWS = 50


class LiveRenderer:
    """Manages ephemeral rendering of agent-generated code artifacts."""

    def __init__(self, serve_dir: str = "data/previews") -> None:
        """Initializes the Live Renderer.

        Args:
            serve_dir: Directory for persisted preview files.
        """
        self.serve_dir = Path(serve_dir)
        self.serve_dir.mkdir(parents=True, exist_ok=True)
        logger.info("live_renderer_initialized", serve_dir=str(self.serve_dir))

    def detect_language(self, code: str) -> str:
        """Detects the language/framework of generated code.

        Args:
            code: The raw code string from an agent.

        Returns:
            One of: 'html', 'python', 'react', 'javascript', 'css', 'unknown'.
        """
        code_lower = code.strip().lower()

        # HTML detection
        if re.search(r'<!doctype\s+html|<html|<body|<div|<head', code_lower):
            return 'html'

        # React detection (JSX patterns)
        if re.search(r'import\s+react|from\s+["\']react["\']|jsx|<\w+\s+className=', code):
            return 'react'

        # Python detection
        if re.search(r'^(import |from |def |class |print\(|if __name__)', code, re.MULTILINE):
            return 'python'

        # JavaScript detection
        if re.search(r'(const |let |var |function |=>|document\.)', code):
            return 'javascript'

        # CSS detection
        if re.search(r'(\{[^}]*:[^}]*;[^}]*\}|@media|@keyframes)', code):
            return 'css'

        return 'unknown'

    def extract_renderable_blocks(self, agent_output: str) -> List[Dict[str, str]]:
        """Extracts all renderable code blocks from agent output.

        Parses markdown code fences and identifies renderable artifacts.

        Args:
            agent_output: Raw agent response text (may contain markdown).

        Returns:
            List of dicts with 'language' and 'code' keys.
        """
        blocks = []
        # Match ```lang\n...\n``` blocks
        pattern = r'```(\w*)\s*\n(.*?)```'
        matches = re.findall(pattern, agent_output, re.DOTALL)

        for lang_hint, code in matches:
            lang_hint = lang_hint.lower().strip()

            # Map common hints
            lang_map = {
                'html': 'html', 'htm': 'html',
                'python': 'python', 'py': 'python',
                'javascript': 'javascript', 'js': 'javascript',
                'jsx': 'react', 'tsx': 'react', 'react': 'react',
                'css': 'css',
            }

            detected = lang_map.get(lang_hint, self.detect_language(code))

            if detected != 'unknown':
                blocks.append({'language': detected, 'code': code.strip()})

        # If no fenced blocks, try the whole output
        if not blocks:
            detected = self.detect_language(agent_output)
            if detected != 'unknown':
                blocks.append({'language': detected, 'code': agent_output.strip()})

        logger.info("renderable_blocks_extracted", count=len(blocks))
        return blocks

    def render_html(self, code: str, title: str = "SAGE Preview") -> str:
        """Wraps raw HTML/CSS/JS in a complete sandboxed document.

        Args:
            code: HTML code (may include <style> and <script>).
            title: Page title.

        Returns:
            Complete HTML document string.
        """
        # If it's already a complete document, return as-is
        if re.search(r'<!doctype|<html', code, re.IGNORECASE):
            return code

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', system-ui, sans-serif; background: #0a0a0a; color: #e0e0e0; }}
    </style>
</head>
<body>
{code}
</body>
</html>"""

    def render_python_pyodide(self, code: str) -> str:
        """Wraps Python code in a Pyodide-powered HTML page.

        The code runs entirely client-side via WebAssembly —
        no server-side execution needed.

        Args:
            code: Python source code.

        Returns:
            Complete HTML document with embedded Pyodide runtime.
        """
        escaped_code = html.escape(code)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SAGE Python Preview</title>
    <script src="https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'JetBrains Mono', monospace; background: #0d1117; color: #c9d1d9; padding: 16px; }}
        #output {{ white-space: pre-wrap; font-size: 14px; line-height: 1.6; }}
        #status {{ color: #58a6ff; margin-bottom: 12px; font-size: 12px; }}
        .error {{ color: #f85149; }}
        .plot-container {{ margin-top: 16px; }}
        .plot-container img {{ max-width: 100%; border-radius: 8px; }}
    </style>
</head>
<body>
    <div id="status">⏳ Loading Python runtime...</div>
    <div id="output"></div>
    <div id="plot-container" class="plot-container"></div>
    <script>
        async function main() {{
            const outputEl = document.getElementById('output');
            const statusEl = document.getElementById('status');
            const plotEl = document.getElementById('plot-container');

            try {{
                let pyodide = await loadPyodide({{
                    stdout: (text) => {{ outputEl.textContent += text + '\\n'; }},
                    stderr: (text) => {{ outputEl.innerHTML += '<span class="error">' + text + '</span>\\n'; }}
                }});

                // Pre-install common packages
                await pyodide.loadPackage(['numpy', 'micropip']);
                statusEl.textContent = '✅ Python ready — executing...';

                // Redirect matplotlib to base64 PNG
                await pyodide.runPythonAsync(`
import sys, io
_sage_stdout = io.StringIO()
`);

                await pyodide.runPythonAsync(`{escaped_code}`);
                statusEl.textContent = '✅ Execution complete';

                // Check for matplotlib figures
                try {{
                    const plotData = await pyodide.runPythonAsync(`
try:
    import matplotlib.pyplot as plt
    import base64, io
    figs = [plt.figure(i) for i in plt.get_fignums()]
    plots = []
    for fig in figs:
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                    facecolor='#0d1117', edgecolor='none')
        buf.seek(0)
        plots.append(base64.b64encode(buf.read()).decode())
    '|||'.join(plots)
except:
    ''
`);
                    if (plotData) {{
                        plotData.split('|||').forEach(b64 => {{
                            if (b64) {{
                                const img = document.createElement('img');
                                img.src = 'data:image/png;base64,' + b64;
                                plotEl.appendChild(img);
                            }}
                        }});
                    }}
                }} catch(e) {{}}

            }} catch (err) {{
                statusEl.textContent = '❌ Error';
                outputEl.innerHTML = '<span class="error">' + err.message + '</span>';
            }}
        }}
        main();
    </script>
</body>
</html>"""

    def render_react_esm(self, code: str) -> str:
        """Wraps React/JSX code in an ESM-powered standalone page.

        Uses esm.sh CDN for zero-build React rendering.

        Args:
            code: React component code (JSX).

        Returns:
            Complete HTML document with embedded React via ESM.
        """
        escaped_code = code.replace('`', '\\`').replace('${', '\\${')
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SAGE React Preview</title>
    <script type="importmap">
    {{
        "imports": {{
            "react": "https://esm.sh/react@18",
            "react-dom/client": "https://esm.sh/react-dom@18/client",
            "react/jsx-runtime": "https://esm.sh/react@18/jsx-runtime"
        }}
    }}
    </script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', system-ui, sans-serif; background: #0a0a0a; color: #e0e0e0; }}
        #root {{ min-height: 100vh; }}
    </style>
</head>
<body>
    <div id="root"></div>
    <script type="module">
        import React from 'react';
        import {{ createRoot }} from 'react-dom/client';

        // Babel standalone for JSX transpilation
        const babelScript = document.createElement('script');
        babelScript.src = 'https://unpkg.com/@babel/standalone/babel.min.js';
        babelScript.onload = () => {{
            try {{
                const code = `{escaped_code}`;
                const transformed = Babel.transform(code, {{
                    presets: ['react'],
                    plugins: []
                }}).code;

                const module = {{ exports: {{}} }};
                const fn = new Function('React', 'module', 'exports', transformed);
                fn(React, module, module.exports);

                const Component = module.exports.default || module.exports;
                const root = createRoot(document.getElementById('root'));
                root.render(React.createElement(Component));
            }} catch(e) {{
                document.getElementById('root').innerHTML =
                    '<pre style="color:#f85149;padding:16px">' + e.message + '</pre>';
            }}
        }};
        document.head.appendChild(babelScript);
    </script>
</body>
</html>"""

    def render_javascript(self, code: str) -> str:
        """Wraps vanilla JavaScript in an HTML page with a canvas and output div.

        Args:
            code: JavaScript source code.

        Returns:
            Complete HTML document.
        """
        escaped_code = html.escape(code)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SAGE JS Preview</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', system-ui, sans-serif; background: #0a0a0a; color: #e0e0e0; padding: 16px; }}
        canvas {{ border: 1px solid #333; border-radius: 8px; display: block; margin: 16px auto; }}
        #output {{ white-space: pre-wrap; font-family: 'JetBrains Mono', monospace; font-size: 14px; padding: 16px; }}
    </style>
</head>
<body>
    <canvas id="canvas" width="800" height="600"></canvas>
    <div id="output"></div>
    <script>
        const _origLog = console.log;
        console.log = function(...args) {{
            _origLog(...args);
            document.getElementById('output').textContent += args.join(' ') + '\\n';
        }};
        try {{
            {code}
        }} catch(e) {{
            document.getElementById('output').innerHTML =
                '<span style="color:#f85149">' + e.message + '</span>';
        }}
    </script>
</body>
</html>"""

    async def render(
        self,
        agent_output: str,
        session_id: str = "default",
    ) -> List[Dict[str, Any]]:
        """Main entry point: extracts and renders all code blocks from agent output.

        Args:
            agent_output: Full agent response text.
            session_id: Session identifier for namespacing.

        Returns:
            List of preview descriptors with 'preview_id', 'language',
            'html_content', and 'preview_url'.
        """
        blocks = self.extract_renderable_blocks(agent_output)
        previews = []

        for i, block in enumerate(blocks):
            lang = block['language']
            code = block['code']

            # Generate deterministic preview ID
            content_hash = hashlib.sha256(code.encode()).hexdigest()[:12]
            preview_id = f"{session_id}_{lang}_{content_hash}"

            # Render based on language
            if lang == 'html':
                rendered = self.render_html(code)
            elif lang == 'python':
                rendered = self.render_python_pyodide(code)
            elif lang == 'react':
                rendered = self.render_react_esm(code)
            elif lang == 'javascript':
                rendered = self.render_javascript(code)
            elif lang == 'css':
                # CSS-only: wrap in minimal HTML
                rendered = self.render_html(f"<style>{code}</style><div class='preview'>CSS Preview</div>")
            else:
                continue

            # Store in memory
            _preview_store[preview_id] = {
                'html': rendered,
                'language': lang,
                'created_at': time.time(),
                'session_id': session_id,
            }

            # Also persist to disk for static serving
            preview_file = self.serve_dir / f"{preview_id}.html"
            preview_file.write_text(rendered, encoding='utf-8')

            previews.append({
                'preview_id': preview_id,
                'language': lang,
                'html_content': rendered,
                'preview_url': f"/preview/{preview_id}",
            })

            logger.info(
                "preview_rendered",
                preview_id=preview_id,
                language=lang,
                size_bytes=len(rendered),
            )

        # LRU eviction
        if len(_preview_store) > MAX_PREVIEWS:
            sorted_keys = sorted(
                _preview_store.keys(),
                key=lambda k: _preview_store[k]['created_at']
            )
            for old_key in sorted_keys[:len(_preview_store) - MAX_PREVIEWS]:
                del _preview_store[old_key]
                old_file = self.serve_dir / f"{old_key}.html"
                if old_file.exists():
                    old_file.unlink()

        return previews


def get_preview(preview_id: str) -> Optional[str]:
    """Retrieves a rendered preview by ID.

    Args:
        preview_id: The preview identifier.

    Returns:
        HTML content string, or None if not found.
    """
    entry = _preview_store.get(preview_id)
    if entry:
        return entry['html']
    return None
