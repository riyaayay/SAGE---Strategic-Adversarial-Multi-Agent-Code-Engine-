import pytest
import shutil
import asyncio
from sage.tools.sandbox import run_in_sandbox
from sage.core.types import ToolReport

@pytest.mark.asyncio
async def test_sandbox_blocks_network() -> None:
    """Asserts that the sandbox prevents network access."""
    if not (shutil.which("firejail") or shutil.which("bwrap")):
        pytest.skip("No sandbox tool (firejail/bwrap) available to enforce network isolation.")
    
    code = """
import urllib.request
def leak():
    urllib.request.urlopen("http://example.com", timeout=2)
"""
    tests = """
def test_leak():
    leak()
"""
    # If network is blocked, this should raise URLError/Timeout
    report = await run_in_sandbox(code, tests, timeout=5)
    assert not report.tests_passed

@pytest.mark.asyncio
async def test_sandbox_blocks_filesystem_escape() -> None:
    """Asserts that the sandbox prevents access to sensitive system files."""
    if not (shutil.which("firejail") or shutil.which("bwrap")):
        pytest.skip("No sandbox tool available to enforce filesystem isolation.")
        
    code = """
def escape():
    with open("/etc/passwd", "r") as f:
        return f.read()
"""
    tests = """
def test_escape():
    escape()
"""
    report = await run_in_sandbox(code, tests, timeout=5)
    assert not report.tests_passed

@pytest.mark.asyncio
async def test_sandbox_enforces_timeout() -> None:
    """Asserts that infinite loops are killed within the timeout margin."""
    code = """
def infinite():
    while True:
        pass
"""
    tests = """
def test_infinite():
    infinite()
"""
    # We set a short timeout and check if it returns a failure report
    report = await run_in_sandbox(code, tests, timeout=2)
    assert not report.tests_passed
    assert report.total_damage >= 0.5

@pytest.mark.asyncio
async def test_sandbox_memory_limit() -> None:
    """Asserts that high memory allocation is killed (1GB limit)."""
    if not (shutil.which("firejail") or shutil.which("bwrap")):
        pytest.skip("No sandbox tool available to enforce memory limits.")
        
    code = """
def memory_hog():
    # Attempt to allocate ~2GB
    a = [0] * (2 * 1024 * 1024 * 1024 // 8)
    return len(a)
"""
    tests = """
def test_memory():
    memory_hog()
"""
    report = await run_in_sandbox(code, tests, timeout=10)
    assert not report.tests_passed

@pytest.mark.asyncio
async def test_sandbox_returns_structured_report_on_crash() -> None:
    """Asserts that hard crashes return a valid ToolReport."""
    code = """
import os
def crash():
    os._exit(1)
"""
    tests = """
def test_crash():
    crash()
"""
    report = await run_in_sandbox(code, tests, timeout=5)
    assert isinstance(report, ToolReport)
    assert not report.tests_passed
