#!/usr/bin/env python3
"""Quick validation script for SAGE app.py (v3.0)"""
import ast
import sys
import os

# Fix Windows console encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def validate():
    with open("app.py", "r", encoding="utf-8") as f:
        code = f.read()

    ok = True

    # Syntax
    try:
        ast.parse(code)
        print("[OK] Syntax: PASS")
    except SyntaxError as e:
        print(f"[FAIL] Syntax: FAIL -- {e}")
        return 1

    # Imports
    required = ["gradio", "httpx", "matplotlib", "numpy"]
    for mod in required:
        if f"import {mod}" in code or f"from {mod}" in code:
            print(f"[OK] Import {mod}: FOUND")
        else:
            print(f"[WARN] Import {mod}: NOT FOUND")

    # Key classes
    classes = [
        "SageConfig", "BackendClient", "SAGEProAPIClient",
        "OllamaClient", "DemoClient", "VisualizationEngine",
    ]
    for cls in classes:
        if f"class {cls}" in code:
            print(f"[OK] Class {cls}: FOUND")
        else:
            print(f"[FAIL] Class {cls}: MISSING")
            ok = False

    # v3.0 Feature methods
    v3_features = [
        ("render_code", "Glass Renderer"),
        ("vision_debug", "Vision Debugger"),
        ("toggle_dreamer", "Chaos Dreamer Toggle"),
        ("get_dreamer_stats", "Chaos Dreamer Stats"),
        ("_chat_stream", "Streaming Chat (split)"),
    ]
    for method, label in v3_features:
        if method in code:
            print(f"[OK] v3 Feature [{label}]: FOUND")
        else:
            print(f"[FAIL] v3 Feature [{label}]: MISSING")
            ok = False

    # v3.0 UI Tabs
    v3_tabs = ["Live Preview", "Vision Debugger", "Chaos Dreamer"]
    for tab in v3_tabs:
        if tab in code:
            print(f"[OK] UI Tab [{tab}]: FOUND")
        else:
            print(f"[FAIL] UI Tab [{tab}]: MISSING")
            ok = False

    if ok:
        print("\nAll validations passed! (v3.0)")
        return 0
    else:
        print("\nSome validations FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(validate())
