#!/usr/bin/env python3
"""
MCP Server for agent-browser (Playwright-compatible tools)
==========================================================

Provides Playwright-compatible MCP tool names using agent-browser CLI.
This keeps existing prompts/tool names intact while switching the
browser engine to agent-browser.
"""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field


PROJECT_DIR = Path(os.environ.get("PROJECT_DIR", ".")).resolve()
SESSION_NAME = PROJECT_DIR.name or "default"

mcp = FastMCP("playwright")

REF_PATTERN = re.compile(r"(?:ref=)?(@?e\d+)", re.IGNORECASE)


def _normalize_ref(ref: str) -> str:
    if ref.startswith("@"):
        return ref
    match = REF_PATTERN.search(ref)
    if match:
        return f"@{match.group(1).lstrip('@')}"
    return f"@{ref}"


def _selector_from_ref_or_element(ref: Optional[str], element: Optional[str]) -> Optional[str]:
    if ref:
        return _normalize_ref(ref)
    return element


def _run_agent_browser(args: list[str], timeout: int = 60) -> dict:
    cmd = ["agent-browser", "--json", *args]
    env = os.environ.copy()
    env["AGENT_BROWSER_SESSION"] = SESSION_NAME

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "agent-browser command failed")

    output = result.stdout.strip()
    if not output:
        return {"success": True}

    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return {"success": True, "raw": output}

    if payload.get("success") is False:
        raise RuntimeError(payload.get("error") or "agent-browser error")

    return payload


class FormField(BaseModel):
    name: Optional[str] = None
    ref: Optional[str] = None
    type: str
    value: Optional[object] = None


@mcp.tool()
def browser_navigate(
    url: Annotated[str, Field(description="The URL to navigate to")],
) -> str:
    """Navigate to a URL."""
    result = _run_agent_browser(["open", url], timeout=90)
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_navigate_back() -> str:
    """Go back to the previous page."""
    result = _run_agent_browser(["back"])
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_snapshot(
    filename: Annotated[Optional[str], Field(description="Save snapshot to markdown file instead of returning it")] = None,
) -> str:
    """Capture accessibility snapshot (interactive elements)."""
    result = _run_agent_browser(["snapshot", "-i"])
    data = result.get("data", {})
    snapshot = data.get("snapshot", "")

    if filename:
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(snapshot, encoding="utf-8")
        return json.dumps({"saved": str(path), "chars": len(snapshot)}, indent=2)

    return json.dumps(result, indent=2)


@mcp.tool()
def browser_click(
    element: Annotated[str, Field(description="Human-readable element description used to obtain permission to interact with the element")],
    ref: Annotated[str, Field(description="Exact target element reference from the page snapshot")],
    button: Annotated[Optional[str], Field(description="Button to click, defaults to left")] = None,
    doubleClick: Annotated[Optional[bool], Field(description="Whether to perform a double click instead of a single click")] = None,
    modifiers: Annotated[Optional[list[str]], Field(description="Modifier keys to press")] = None,
) -> str:
    """Click an element."""
    selector = _selector_from_ref_or_element(ref, element)
    if not selector:
        raise RuntimeError("No selector or ref provided for click")

    command = "dblclick" if doubleClick else "click"
    result = _run_agent_browser([command, selector])
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_type(
    element: Annotated[str, Field(description="Human-readable element description used to obtain permission to interact with the element")],
    ref: Annotated[str, Field(description="Exact target element reference from the page snapshot")],
    text: Annotated[str, Field(description="Text to type into the element")],
    slowly: Annotated[Optional[bool], Field(description="Whether to type one character at a time")] = None,
    submit: Annotated[Optional[bool], Field(description="Whether to submit entered text (press Enter after)")] = None,
) -> str:
    """Type text into an element."""
    selector = _selector_from_ref_or_element(ref, element)
    if not selector:
        raise RuntimeError("No selector or ref provided for type")

    result = _run_agent_browser(["type", selector, text])
    if submit:
        _run_agent_browser(["press", "Enter"])
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_fill_form(
    fields: Annotated[list[FormField], Field(description="Fields to fill in")],
) -> str:
    """Fill multiple form fields."""
    results = []
    for field in fields:
        selector = _selector_from_ref_or_element(field.ref, None)
        if not selector and field.name:
            selector = f'[name="{field.name}"]'
        if not selector:
            results.append({"field": field.name, "status": "skipped", "reason": "no selector"})
            continue

        field_type = (field.type or "").lower()
        value = field.value

        if field_type == "checkbox":
            action = "check" if value in (True, "true", "1", 1) else "uncheck"
            result = _run_agent_browser([action, selector])
        elif field_type in ("combobox", "select", "dropdown"):
            if value is None:
                results.append({"field": field.name, "status": "skipped", "reason": "no value"})
                continue
            result = _run_agent_browser(["select", selector, str(value)])
        else:
            result = _run_agent_browser(["fill", selector, "" if value is None else str(value)])

        results.append({"field": field.name, "status": "ok", "result": result})

    return json.dumps({"results": results}, indent=2)


@mcp.tool()
def browser_select_option(
    element: Annotated[str, Field(description="Human-readable element description used to obtain permission to interact with the element")],
    ref: Annotated[str, Field(description="Exact target element reference from the page snapshot")],
    values: Annotated[list[str], Field(description="Array of values to select in the dropdown")],
) -> str:
    """Select a dropdown option."""
    selector = _selector_from_ref_or_element(ref, element)
    if not selector:
        raise RuntimeError("No selector or ref provided for select")

    if not values:
        raise RuntimeError("No values provided for select")

    result = _run_agent_browser(["select", selector, values[0]])
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_hover(
    element: Annotated[str, Field(description="Human-readable element description used to obtain permission to interact with the element")],
    ref: Annotated[str, Field(description="Exact target element reference from the page snapshot")],
) -> str:
    """Hover over an element."""
    selector = _selector_from_ref_or_element(ref, element)
    if not selector:
        raise RuntimeError("No selector or ref provided for hover")
    result = _run_agent_browser(["hover", selector])
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_drag(
    startElement: Annotated[str, Field(description="Human-readable source element description used to obtain the permission to interact with the element")],
    startRef: Annotated[str, Field(description="Exact source element reference from the page snapshot")],
    endElement: Annotated[str, Field(description="Human-readable target element description used to obtain the permission to interact with the element")],
    endRef: Annotated[str, Field(description="Exact target element reference from the page snapshot")],
) -> str:
    """Drag and drop between two elements."""
    source = _selector_from_ref_or_element(startRef, startElement)
    target = _selector_from_ref_or_element(endRef, endElement)
    if not source or not target:
        raise RuntimeError("Missing source or target selector for drag")
    result = _run_agent_browser(["drag", source, target])
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_press_key(
    key: Annotated[str, Field(description="Name of the key to press or a character to generate")],
) -> str:
    """Press a key on the keyboard."""
    result = _run_agent_browser(["press", key])
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_evaluate(
    function: Annotated[str, Field(description="() => { /* code */ } or (element) => { /* code */ }")],
    element: Annotated[Optional[str], Field(description="Human-readable element description used to obtain permission to interact with the element")] = None,
    ref: Annotated[Optional[str], Field(description="Exact target element reference from the page snapshot")] = None,
) -> str:
    """Evaluate JavaScript on the page."""
    script = function.strip()
    if "=>" in script and not script.rstrip().endswith(")()"):
        script = f"({script})()"
    result = _run_agent_browser(["eval", script])
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_console_messages(
    level: Annotated[Optional[str], Field(description="Level of the console messages to return")] = None,
) -> str:
    """Return console messages."""
    result = _run_agent_browser(["console"])
    data = result.get("data", {})
    if level and isinstance(data.get("messages"), list):
        data["messages"] = [m for m in data["messages"] if m.get("type") == level]
        result["data"] = data
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_network_requests(
    includeStatic: Annotated[Optional[bool], Field(description="Whether to include successful static resources like images, fonts, scripts, etc.")] = None,
) -> str:
    """Return tracked network requests."""
    result = _run_agent_browser(["network", "requests"])
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_close() -> str:
    """Close the browser."""
    result = _run_agent_browser(["close"])
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_resize(
    width: Annotated[int, Field(description="Width of the browser window")],
    height: Annotated[int, Field(description="Height of the browser window")],
) -> str:
    """Resize the browser window."""
    result = _run_agent_browser(["set", "viewport", str(width), str(height)])
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_tabs(
    action: Annotated[str, Field(description="Operation to perform")],
    index: Annotated[Optional[int], Field(description="Tab index, used for close/select")] = None,
) -> str:
    """List, create, close, or select a browser tab."""
    action_lower = action.lower()
    if action_lower == "new":
        args = ["tab", "new"]
    elif action_lower in ("list", "ls"):
        args = ["tab", "list"]
    elif action_lower in ("select", "switch"):
        if index is None:
            raise RuntimeError("index is required for select")
        args = ["tab", str(index)]
    elif action_lower == "close":
        args = ["tab", "close"]
        if index is not None:
            args.append(str(index))
    else:
        args = ["tab", "list"]
    result = _run_agent_browser(args)
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_wait_for(
    text: Annotated[Optional[str], Field(description="The text to wait for")] = None,
    textGone: Annotated[Optional[str], Field(description="The text to wait for to disappear")] = None,
    time: Annotated[Optional[float], Field(description="The time to wait in seconds")] = None,
) -> str:
    """Wait for text or time."""
    if text:
        result = _run_agent_browser(["wait", "--text", text])
    elif textGone:
        expr = f"!document.body || !document.body.innerText.includes({json.dumps(textGone)})"
        result = _run_agent_browser(["wait", "--fn", expr])
    elif time is not None:
        milliseconds = int(time * 1000)
        result = _run_agent_browser(["wait", str(milliseconds)])
    else:
        result = _run_agent_browser(["wait", "--load", "networkidle"])
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_handle_dialog(
    accept: Annotated[bool, Field(description="Whether to accept the dialog.")],
    promptText: Annotated[Optional[str], Field(description="The text of the prompt in case of a prompt dialog.")] = None,
) -> str:
    """Handle a dialog."""
    if accept:
        args = ["dialog", "accept"]
        if promptText:
            args.append(promptText)
    else:
        args = ["dialog", "dismiss"]
    result = _run_agent_browser(args)
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_file_upload(
    paths: Annotated[Optional[list[str]], Field(description="The absolute paths to the files to upload. Can be single file or multiple files.")] = None,
    selector: Annotated[Optional[str], Field(description="CSS selector for file input")] = None,
) -> str:
    """Upload one or multiple files."""
    if not paths:
        raise RuntimeError("No files provided for upload")
    file_selector = selector or "input[type=\"file\"]"
    result = _run_agent_browser(["upload", file_selector, *paths])
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_take_screenshot(
    filename: Annotated[Optional[str], Field(description="File name to save the screenshot to")] = None,
    fullPage: Annotated[Optional[bool], Field(description="When true, takes a screenshot of the full scrollable page")] = None,
    element: Annotated[Optional[str], Field(description="Human-readable element description used to obtain permission to screenshot the element")] = None,
    ref: Annotated[Optional[str], Field(description="Exact target element reference from the page snapshot.")] = None,
    type: Annotated[Optional[str], Field(description="Image format for the screenshot. Default is png.")] = None,
) -> str:
    """Take a screenshot of the current page."""
    args = ["screenshot"]
    if fullPage:
        args.append("--full")
    if filename:
        args.append(filename)
    result = _run_agent_browser(args, timeout=90)
    return json.dumps(result, indent=2)


@mcp.tool()
def browser_install() -> str:
    """Install the browser."""
    result = _run_agent_browser(["install"])
    return json.dumps(result, indent=2)
