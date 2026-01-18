"""
Spec Update Service
===================

Analyzes large requirements documents, extracts structured requirements,
produces a proposed app_spec, and stores analysis artifacts for later apply.
"""

import json
import logging
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent.parent.parent

EXTRACTION_PROMPT_TEMPLATE = """You are extracting software requirements from a document chunk.

Section path: {section_path}
Chunk id: {chunk_id}

<chunk>
{chunk_content}
</chunk>

Return a JSON array. Each item must include:
- req_id: unique id (string)
- title: short requirement title
- description: 1-3 sentences
- acceptance: list of acceptance criteria (strings)
- constraints: list of constraints (strings)
- priority: one of low|medium|high
- tags: list of short tags (strings)
- source_anchor: reference to section or line context (string)

If no requirements exist, return []. Output ONLY JSON."""

SYNTHESIS_PROMPT_TEMPLATE = """You are generating an updated app_spec.txt based on extracted requirements.

Requirements (JSON array):
{requirements_json}

Existing app_spec (optional, keep structure consistent):
<spec>
{existing_spec}
</spec>

Task:
- Produce a complete app_spec.txt in valid XML.
- Include all required sections.
- Ensure core_features reflects the requirements.
- Do not include any extra text outside XML.
"""


@dataclass
class RequirementChunk:
    chunk_id: str
    section_path: str
    content: str


@dataclass
class RequirementItem:
    req_id: str
    title: str
    description: str
    acceptance: list[str]
    constraints: list[str]
    priority: str
    tags: list[str]
    source_anchor: str


class SpecUpdateAnalyzer:
    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        temp_dir: Optional[Path] = None,
    ):
        self.model = model
        self.temp_dir = temp_dir or Path.home() / ".auto-agent-harness" / "spec_update"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def analyze(self, input_text: str, existing_spec: str | None = None) -> dict:
        chunks = chunk_text(input_text)
        requirements: list[RequirementItem] = []
        coverage = build_coverage_map(chunks)

        for chunk in chunks:
            extracted = await self._extract_chunk(chunk)
            requirements.extend(extracted)
            if chunk.section_path in coverage:
                coverage[chunk.section_path]["requirements"] += len(extracted)

        normalized = normalize_requirements(requirements)
        proposed_spec = await self._synthesize_spec(normalized, existing_spec or "")
        diff_summary = diff_specs(existing_spec or "", proposed_spec)

        return {
            "requirements": [req.__dict__ for req in normalized],
            "coverage": [
                {
                    "section": section,
                    "chunks": data["chunks"],
                    "requirements": data["requirements"],
                }
                for section, data in coverage.items()
            ],
            "proposed_spec": proposed_spec,
            "diff": diff_summary,
        }

    async def _extract_chunk(self, chunk: RequirementChunk) -> list[RequirementItem]:
        prompt = EXTRACTION_PROMPT_TEMPLATE.format(
            section_path=chunk.section_path,
            chunk_id=chunk.chunk_id,
            chunk_content=chunk.content,
        )
        response_text = await self._query_claude(prompt)
        data = parse_json_payload(response_text)
        if not isinstance(data, list):
            return []

        extracted: list[RequirementItem] = []
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            extracted.append(build_requirement_item(item, chunk, idx))
        return extracted

    async def _synthesize_spec(self, requirements: list[RequirementItem], existing_spec: str) -> str:
        requirements_json = json.dumps([req.__dict__ for req in requirements], ensure_ascii=True)
        prompt = SYNTHESIS_PROMPT_TEMPLATE.format(
            requirements_json=requirements_json,
            existing_spec=existing_spec,
        )
        return await self._query_claude(prompt)

    async def _query_claude(self, prompt: str) -> str:
        work_dir = self.temp_dir / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        work_dir.mkdir(parents=True, exist_ok=True)

        settings = {
            "sandbox": {"enabled": False},
            "permissions": {"defaultMode": "acceptEdits", "allow": []},
        }
        settings_file = work_dir / ".claude_settings.json"
        settings_file.write_text(json.dumps(settings), encoding="utf-8")

        system_cli = shutil.which("claude")

        client = ClaudeSDKClient(
            options=ClaudeAgentOptions(
                model=self.model,
                cli_path=system_cli,
                system_prompt="You are a senior product analyst.",
                allowed_tools=[],
                max_turns=1,
                cwd=str(work_dir.resolve()),
                settings=str(settings_file.resolve()),
            )
        )

        response_text = ""
        try:
            async with client:
                await client.query(prompt)
                async for msg in client.receive_response():
                    msg_type = type(msg).__name__
                    if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                        for block in msg.content:
                            if type(block).__name__ == "TextBlock" and hasattr(block, "text"):
                                response_text += block.text
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        return response_text


def build_requirement_item(item: dict, chunk: RequirementChunk, index: int) -> RequirementItem:
    req_id = str(item.get("req_id") or f"{chunk.chunk_id}-{index}")
    title = str(item.get("title") or "Untitled requirement").strip()
    description = str(item.get("description") or "").strip() or title
    acceptance = list(filter(None, item.get("acceptance") or []))
    constraints = list(filter(None, item.get("constraints") or []))
    priority = str(item.get("priority") or "medium").lower()
    if priority not in {"low", "medium", "high"}:
        priority = "medium"
    tags = list(filter(None, item.get("tags") or []))
    source_anchor = str(item.get("source_anchor") or chunk.section_path)

    return RequirementItem(
        req_id=req_id,
        title=title,
        description=description,
        acceptance=acceptance,
        constraints=constraints,
        priority=priority,
        tags=tags,
        source_anchor=source_anchor,
    )


def normalize_requirements(requirements: Iterable[RequirementItem]) -> list[RequirementItem]:
    normalized: list[RequirementItem] = []
    seen_keys: set[str] = set()
    for req in requirements:
        key = normalize_text(req.title)
        if not key:
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        normalized.append(req)
    return normalized


def chunk_text(text: str, max_chars: int = 4000) -> list[RequirementChunk]:
    lines = text.splitlines()
    chunks: list[RequirementChunk] = []
    section_title = "Document"
    section_lines: list[str] = []
    section_index = 0

    def flush_section(lines_buffer: list[str]) -> None:
        nonlocal section_index
        if not lines_buffer:
            return
        content = "\n".join(lines_buffer).strip()
        if not content:
            return
        current = content
        while len(current) > max_chars:
            part = current[:max_chars]
            current = current[max_chars:]
            chunk_id = f"sec{section_index}_part{len(chunks)}"
            chunks.append(RequirementChunk(chunk_id=chunk_id, section_path=section_title, content=part))
        if current:
            chunk_id = f"sec{section_index}_part{len(chunks)}"
            chunks.append(RequirementChunk(chunk_id=chunk_id, section_path=section_title, content=current))
        section_index += 1

    for line in lines:
        heading_match = re.match(r"^\s{0,3}(#{1,6})\s+(.*)$", line)
        if heading_match:
            flush_section(section_lines)
            section_title = heading_match.group(2).strip() or "Section"
            section_lines = []
            continue
        section_lines.append(line)

    flush_section(section_lines)

    if not chunks:
        chunks.append(RequirementChunk(chunk_id="sec0_part0", section_path=section_title, content=text))

    return chunks


def build_coverage_map(chunks: list[RequirementChunk]) -> dict[str, dict[str, int]]:
    coverage: dict[str, dict[str, int]] = {}
    for chunk in chunks:
        section = chunk.section_path
        if section not in coverage:
            coverage[section] = {"chunks": 0, "requirements": 0}
        coverage[section]["chunks"] += 1
    return coverage


def parse_json_payload(text: str) -> Any:
    if "```" in text:
        match = re.search(r"```json\s*(.+?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1)
    text = text.strip()
    start_idx = min([i for i in [text.find("["), text.find("{")] if i != -1], default=-1)
    if start_idx == -1:
        return None
    payload = text[start_idx:]
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        end_idx = max(payload.rfind("]"), payload.rfind("}"))
        if end_idx != -1:
            try:
                return json.loads(payload[: end_idx + 1])
            except json.JSONDecodeError:
                return None
    return None


def diff_specs(existing_spec: str, proposed_spec: str) -> dict:
    sections = [
        "project_name",
        "overview",
        "technology_stack",
        "feature_count",
        "core_features",
        "database_schema",
        "api_endpoints",
        "implementation_steps",
        "success_criteria",
    ]
    changes = []
    for section in sections:
        old = extract_xml_section(existing_spec, section)
        new = extract_xml_section(proposed_spec, section)
        if normalize_text(old) == normalize_text(new):
            continue
        change_type = "cosmetic" if normalize_text(old, strict=True) == normalize_text(new, strict=True) else "logic"
        changes.append({"section": section, "change_type": change_type})
    return {"changes": changes, "change_count": len(changes)}


def extract_xml_section(spec: str, tag: str) -> str:
    if not spec:
        return ""
    match = re.search(rf"<{tag}>(.*?)</{tag}>", spec, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def normalize_text(value: str, strict: bool = False) -> str:
    if not value:
        return ""
    normalized = value.lower()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if strict:
        normalized = re.sub(r"[^a-z0-9 ]", "", normalized)
    return normalized


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a, strict=True), normalize_text(b, strict=True)).ratio()


def build_analysis_id() -> str:
    return f"spec_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def store_analysis(project_dir: Path, analysis_id: str, payload: dict, input_text: str) -> dict:
    prompts_dir = project_dir / "prompts"
    updates_dir = prompts_dir / "spec_updates"
    updates_dir.mkdir(parents=True, exist_ok=True)

    input_file = updates_dir / f"input_{analysis_id}.txt"
    analysis_file = updates_dir / f"analysis_{analysis_id}.json"

    input_file.write_text(input_text, encoding="utf-8")
    payload["input_file"] = str(input_file)
    payload["analysis_file"] = str(analysis_file)
    analysis_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return {
        "input_file": str(input_file),
        "analysis_file": str(analysis_file),
    }


def load_analysis(project_dir: Path, analysis_id: str) -> dict:
    updates_dir = project_dir / "prompts" / "spec_updates"
    analysis_file = updates_dir / f"analysis_{analysis_id}.json"
    if not analysis_file.exists():
        raise FileNotFoundError("Spec update analysis not found")
    return json.loads(analysis_file.read_text(encoding="utf-8"))


def write_spec_version(project_dir: Path, analysis_id: str, proposed_spec: str, diff: dict, notes: str | None) -> dict:
    prompts_dir = project_dir / "prompts"
    versions_dir = prompts_dir / "spec_versions"
    versions_dir.mkdir(parents=True, exist_ok=True)

    spec_file = versions_dir / f"app_spec.{analysis_id}.xml"
    diff_file = versions_dir / f"app_spec.{analysis_id}.diff.json"

    spec_file.write_text(proposed_spec, encoding="utf-8")
    diff_file.write_text(json.dumps(diff, indent=2), encoding="utf-8")

    return {
        "version_id": analysis_id,
        "spec_file": str(spec_file),
        "diff_file": str(diff_file),
        "notes": notes or "",
    }


def add_spec_version_to_manifest(project_dir: Path, version_entry: dict) -> None:
    import sys
    sys.path.insert(0, str(ROOT_DIR))
    from prompts import load_spec_manifest, save_spec_manifest

    manifest = load_spec_manifest(project_dir)
    versions = manifest.get("spec_versions")
    if versions is None:
        manifest["spec_versions"] = []
        versions = manifest["spec_versions"]

    version_entry = {
        "version_id": version_entry["version_id"],
        "created_at": datetime.utcnow().isoformat(),
        "spec_file": version_entry["spec_file"],
        "diff_file": version_entry["diff_file"],
        "input_file": version_entry.get("input_file"),
        "notes": version_entry.get("notes", ""),
    }

    versions.append(version_entry)
    save_spec_manifest(project_dir, manifest)
