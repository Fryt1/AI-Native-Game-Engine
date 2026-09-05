"""Render the final WorkflowPlan / Project Tool / MCP architecture."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "architecture" / "diagrams"
SVG_PATH = OUT / "agent-workflow-toolset-architecture.svg"
PNG_PATH = OUT / "agent-workflow-toolset-architecture.png"
WIDTH, HEIGHT = 2800, 1800

Box = tuple[int, int, int, int, str, list[str], str, str]
BOXES: dict[str, Box] = {
    "intent": (70, 90, 300, 150, "User Intent", ["goal + constraints"], "#173b3d", "#56d6c0"),
    "guidance": (470, 90, 430, 150, "Skill + Workflow Definition", ["guidance + invariants", "reusable plan template"], "#3e315d", "#c8a6ff"),
    "plan": (1000, 90, 480, 150, "Agent WorkflowPlan", ["Steps + Stages", "ordered calls + checklists"], "#173b3d", "#56d6c0"),
    "gate": (1580, 90, 500, 150, "Plan Feasibility Gate", ["Project Tools + MCP calls", "checked before side effects"], "#263c5c", "#8dc7ff"),
    "stage": (940, 390, 920, 220, "Stage", ["local goal", "execution_checklist[]", "acceptance_checklist[]", "calls[] in declared order"], "#173b3d", "#56d6c0"),
    "toolcall": (90, 760, 430, 170, "ToolCall", ["our registered Tool", "toolset_id + tool_id", "arguments"], "#39475a", "#c3d0e8"),
    "registry": (620, 760, 500, 170, "Project Tool Registry", ["our Toolsets + Tools", "AssetsBridge · Validation", "workflow-backed Tools"], "#263c5c", "#8dc7ff"),
    "implementation": (1210, 760, 500, 170, "Tool Implementation", ["native function", "Blender / UE5 script", "ComfyUI workflow"], "#39475a", "#c3d0e8"),
    "mcpcall": (1790, 760, 390, 170, "McpCall", ["server_id + tool_name", "arguments"], "#39475a", "#c3d0e8"),
    "mcp": (2250, 760, 430, 170, "Agent MCP Client", ["configured on the Agent", "tools/list + tools/call"], "#263c5c", "#8dc7ff"),
    "servers": (2130, 1030, 550, 150, "MCP Servers", ["Blender MCP · UE5 MCP", "local process or local service"], "#39475a", "#c3d0e8"),
    "result": (930, 1190, 940, 180, "ExecutionResult + Evidence", ["status · outputs · artifacts", "warnings · errors · resume pointer", "normalized for both call paths"], "#193b2b", "#63d69a"),
    "acceptance": (930, 1460, 940, 150, "Acceptance Evaluator", ["deterministic checks + human review", "StageResult"], "#193b2b", "#63d69a"),
    "next": (930, 1690, 940, 90, "continue · retry · wait · compensate · re-plan", [], "#173b3d", "#56d6c0"),
}

ARROWS = (
    ("intent", "guidance", "right", "left", None),
    ("guidance", "plan", "right", "left", None),
    ("plan", "gate", "right", "left", None),
    ("gate", "stage", "bottom", "top", "ready"),
    ("stage", "toolcall", "bottom", "top", None),
    ("stage", "mcpcall", "bottom", "top", None),
    ("toolcall", "registry", "right", "left", None),
    ("registry", "implementation", "right", "left", None),
    ("mcpcall", "mcp", "right", "left", None),
    ("mcp", "servers", "bottom", "top", None),
    ("implementation", "result", "bottom", "top", None),
    ("servers", "result", "bottom", "top", None),
    ("result", "acceptance", "bottom", "top", None),
    ("acceptance", "next", "bottom", "top", None),
)


def edge(box: Box, side: str) -> tuple[int, int]:
    x, y, w, h, *_ = box
    if side == "left":
        return x, y + h // 2
    if side == "right":
        return x + w, y + h // 2
    if side == "top":
        return x + w // 2, y
    return x + w // 2, y + h


def escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def text(x: int, y: int, value: str, size: int, weight: str = "400", fill: str = "#f8fafc", anchor: str = "middle") -> str:
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="Segoe UI, Arial, sans-serif" font-size="{size}px" font-weight="{weight}" fill="{fill}">{escape(value)}</text>'


def box_svg(box: Box) -> str:
    x, y, w, h, title, lines, fill, stroke = box
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="{fill}" stroke="{stroke}" stroke-width="3"/>']
    parts.append(text(x + w // 2, y + 42, title, 24, "700"))
    for index, line in enumerate(lines):
        parts.append(text(x + w // 2, y + 78 + index * 30, line, 18, "400", "#dbeafe"))
    return "".join(parts)


def arrow_points(source: str, target: str, source_side: str, target_side: str) -> list[tuple[int, int]]:
    sx, sy = edge(BOXES[source], source_side)
    tx, ty = edge(BOXES[target], target_side)
    if source_side == "bottom" and target_side == "top" and sx != tx:
        middle = (sy + ty) // 2
        return [(sx, sy), (sx, middle), (tx, middle), (tx, ty)]
    return [(sx, sy), (tx, ty)]


def arrow_svg(source: str, target: str, source_side: str, target_side: str, label: str | None) -> str:
    points = arrow_points(source, target, source_side, target_side)
    path = " ".join(f"{x},{y}" for x, y in points)
    parts = [f'<polyline points="{path}" fill="none" stroke="#94a3b8" stroke-width="4" marker-end="url(#arrow)"/>']
    if label:
        sx, sy = points[0]
        tx, ty = points[-1]
        parts.append(text((sx + tx) // 2, (sy + ty) // 2 - 10, label, 17, "700", "#cbd5e1"))
    return "".join(parts)


def render_svg() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#0f172a"/>',
        text(70, 45, "Agent WorkflowPlan: Project Tools and MCP are two execution paths", 30, "700", "#56d6c0", "start"),
        text(90, 720, "PROJECT TOOL PATH", 20, "700", "#8dc7ff", "start"),
        text(1790, 720, "DIRECT MCP PATH", 20, "700", "#8dc7ff", "start"),
    ]
    for source, target, source_side, target_side, label in ARROWS:
        parts.append(arrow_svg(source, target, source_side, target_side, label))
    for box in BOXES.values():
        parts.append(box_svg(box))
    parts.append("</svg>")
    SVG_PATH.write_text("".join(parts), encoding="utf-8")


def render_png() -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return
    image = Image.new("RGB", (WIDTH, HEIGHT), "#0f172a")
    draw = ImageDraw.Draw(image)
    font_dir = Path(r"C:\Windows\Fonts")
    regular = ImageFont.truetype(str(font_dir / "segoeui.ttf"), 18)
    bold = ImageFont.truetype(str(font_dir / "segoeuib.ttf"), 24)
    label = ImageFont.truetype(str(font_dir / "segoeuib.ttf"), 30)

    def center(x: int, y: int, value: str, font, fill: str) -> None:
        left, top, right, bottom = draw.textbbox((0, 0), value, font=font)
        draw.text((x - (right - left) / 2, y - (bottom - top) / 2), value, font=font, fill=fill)

    for source, target, source_side, target_side, _ in ARROWS:
        points = arrow_points(source, target, source_side, target_side)
        draw.line(points, fill="#94a3b8", width=4, joint="curve")
        px, py = points[-2]
        tx, ty = points[-1]
        length = max(((tx - px) ** 2 + (ty - py) ** 2) ** 0.5, 1)
        ux, uy = (tx - px) / length, (ty - py) / length
        left = (tx - ux * 15 - uy * 7, ty - uy * 15 + ux * 7)
        right = (tx - ux * 15 + uy * 7, ty - uy * 15 - ux * 7)
        draw.polygon([(tx, ty), left, right], fill="#94a3b8")
    center(730, 38, "Agent WorkflowPlan: Project Tools and MCP are two execution paths", label, "#56d6c0")
    for x, y, w, h, title, lines, fill, stroke in BOXES.values():
        draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=fill, outline=stroke, width=3)
        center(x + w // 2, y + 42, title, bold, "#f8fafc")
        for index, line in enumerate(lines):
            center(x + w // 2, y + 78 + index * 30, line, regular, "#dbeafe")
    image.save(PNG_PATH)


if __name__ == "__main__":
    render_svg()
    render_png()
