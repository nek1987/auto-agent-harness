---
name: mermaid-diagram
version: v1.0.0
description: Generate and validate Mermaid architecture diagrams. Triggers when user requests diagram generation, Mermaid validation, or architecture visualization. Uses mmdc CLI (mermaid-cli v11.12.0).
---

# Mermaid Diagram Skill

**Target Token Efficiency**: 60% (300 tokens → 120 tokens)

## Purpose

Generate PNG/SVG architecture diagrams from Mermaid source files (.mmd) using mmdc CLI, with automatic validation and project-standard theming.

## Trigger Keywords

- "mermaid diagram"
- "generate diagram"
- "아키텍처 다이어그램"
- "다이어그램 생성"
- "mermaid 변환"
- "flowchart 생성"
- "시퀀스 다이어그램"
- "mmd to png"
- "mmd to svg"
- "다이어그램 검증"
- "mermaid validate"

## Context

- **Project**: OpenManager VIBE v5.85.0
- **mmdc Version**: v11.12.0 (@mermaid-js/mermaid-cli)
- **mmdc Path**: `/home/sky-note/.npm-global/bin/mmdc`
- **Theme**: Dark with transparent background
- **Output Scale**: 2x for PNG (high quality)

## Workflow

### 1. Find Mermaid Sources

```bash
# .mmd 파일 검색
find docs/ -name "*.mmd" 2>/dev/null

# 마크다운 내 mermaid 블록 검색
grep -rl '```mermaid' docs/ 2>/dev/null
```

### 2. Validate Mermaid Syntax

```bash
# 문법 검증 (임시 파일로 테스트)
/home/sky-note/.npm-global/bin/mmdc -i [input.mmd] -o /tmp/test.svg 2>&1
```

**Expected Output**:
- ✅ `Generating single mermaid chart` - 문법 유효
- ❌ Error message - 문법 오류, 수정 필요

### 3. Generate Diagrams

```bash
# 출력 디렉토리 생성
mkdir -p [source-dir]/diagrams

# SVG 생성 (웹용, 확대 가능)
/home/sky-note/.npm-global/bin/mmdc \
  -i [input.mmd] \
  -o [source-dir]/diagrams/[name].svg \
  -t dark -b transparent

# PNG 생성 (README용, 2x 스케일)
/home/sky-note/.npm-global/bin/mmdc \
  -i [input.mmd] \
  -o [source-dir]/diagrams/[name].png \
  -t dark -b transparent -s 2
```

### 4. Verify Output

```bash
# 생성된 파일 확인
ls -la [source-dir]/diagrams/
```

**Expected Output**:
```
-rw-r--r-- 1 user user  50000 date [name].png
-rw-r--r-- 1 user user 100000 date [name].svg
```

### 5. Update Documentation

Add image reference to related README:

```markdown
![Architecture Diagram](./diagrams/[name].png)
```

## Report Summary Format

```
🎨 Mermaid Diagram Generation Results
├─ Source: [path/to/file.mmd]
├─ Validation: ✅ Passed / ❌ Failed
├─ PNG: [size]KB (2x scale)
├─ SVG: [size]KB (scalable)
└─ Location: [output-dir]/diagrams/

📋 Files Generated:
1. [name].png - README/마크다운용
2. [name].svg - 웹 문서용
```

## Project Standards

### Color Palette

| 용도 | 색상 | Hex |
|------|------|-----|
| Pages/Primary | 파랑 | `#3b82f6` |
| Components | 녹색 | `#10b981` |
| Hooks | 보라 | `#8b5cf6` |
| Stores | 주황 | `#f59e0b` |
| API | 빨강 | `#ef4444` |
| Data | 청록 | `#06b6d4` |

### Mermaid Init Block (Copy-Paste)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {
  'primaryColor': '#3b82f6',
  'primaryTextColor': '#fff',
  'primaryBorderColor': '#2563eb',
  'lineColor': '#64748b',
  'secondaryColor': '#10b981',
  'tertiaryColor': '#f59e0b'
}}}%%
%% [Feature Name] - Updated YYYY-MM-DD
```

### Diagram Types Reference

| 용도 | Mermaid 타입 | 방향 |
|------|-------------|------|
| 컴포넌트 구조 | `flowchart TB` | Top→Bottom |
| 데이터 흐름 | `flowchart LR` | Left→Right |
| 시퀀스 | `sequenceDiagram` | - |
| 상태 전이 | `stateDiagram-v2` | - |
| DB 스키마 | `erDiagram` | - |

## Existing Diagrams

| Source | Output | Description |
|--------|--------|-------------|
| `docs/core/architecture/system/dashboard-architecture.mmd` | `diagrams/dashboard-architecture.*` | 대시보드 아키텍처 |

## Troubleshooting

**mmdc not found**:
```bash
# 직접 경로 사용
/home/sky-note/.npm-global/bin/mmdc --version

# 또는 PATH 설정
source ~/.bashrc
```

**Syntax Error**:
```bash
# 검증으로 오류 위치 확인
mmdc -i file.mmd -o /tmp/test.svg 2>&1 | head -20
```

**Puppeteer/Chrome Issues**:
```bash
# WSL에서 headless 모드 필요
export PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser
```

## Success Criteria

- Syntax validation: Passed
- PNG file: Created with 2x scale
- SVG file: Created with transparent background
- File sizes: PNG ~50KB+, SVG ~100KB+
- No manual CLI path lookup needed

## Related Resources

- **Memory**: `architecture-diagram-best-practices.md`
- **Example**: `docs/core/architecture/system/dashboard-architecture.mmd`
- **Output**: `docs/core/architecture/system/diagrams/`

## Changelog

- 2025-12-19: v1.0.0 - Initial implementation
  - mmdc v11.12.0 integration
  - Dark theme with project color palette
  - PNG (2x) + SVG dual output
  - Validation workflow
