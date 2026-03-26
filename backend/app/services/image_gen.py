"""Image generation service — renders HTML/CSS to PNG via Playwright."""

from dataclasses import dataclass

from app.models.enums import BuildingType, MemberRole
from app.schemas.board import BoardResponse

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class SiegeMemberWithName:
    name: str
    role: MemberRole
    attack_day: int | None
    has_reserve_set: bool | None


# ---------------------------------------------------------------------------
# Building type colors
# ---------------------------------------------------------------------------

_BUILDING_COLORS: dict[BuildingType, str] = {
    BuildingType.stronghold: "#7c3aed",
    BuildingType.mana_shrine: "#2563eb",
    BuildingType.magic_tower: "#d97706",
    BuildingType.defense_tower: "#16a34a",
    BuildingType.post: "#dc2626",
}

_BUILDING_LABELS: dict[BuildingType, str] = {
    BuildingType.stronghold: "Stronghold",
    BuildingType.mana_shrine: "Mana Shrine",
    BuildingType.magic_tower: "Magic Tower",
    BuildingType.defense_tower: "Defense Tower",
    BuildingType.post: "Post",
}


# ---------------------------------------------------------------------------
# HTML builders (separated from Playwright for testability)
# ---------------------------------------------------------------------------


def _build_assignments_html(board: BoardResponse, siege_date: str) -> str:
    """Build the full assignments board HTML string."""
    # Group buildings by type
    buildings_by_type: dict[BuildingType, list] = {}
    for building in board.buildings:
        bt = BuildingType(building.building_type)
        buildings_by_type.setdefault(bt, []).append(building)

    sections_html = ""
    for bt in BuildingType:
        buildings = buildings_by_type.get(bt, [])
        if not buildings:
            continue

        color = _BUILDING_COLORS[bt]
        label = _BUILDING_LABELS[bt]

        buildings_html = ""
        for bldg in sorted(buildings, key=lambda b: b.building_number):
            rows_html = ""
            for group in sorted(bldg.groups, key=lambda g: g.group_number):
                cells_html = ""
                for pos in sorted(group.positions, key=lambda p: p.position_number):
                    if pos.is_disabled:
                        cell_style = "background:#374151;color:#9ca3af;"
                        cell_text = "N/A"
                    elif pos.is_reserve:
                        cell_style = "background:#92400e;color:#fef3c7;"
                        cell_text = "RESERVE"
                    elif pos.member_name:
                        cell_style = "background:#1f2937;color:#f9fafb;"
                        cell_text = pos.member_name
                    else:
                        cell_style = "background:#111827;color:#6b7280;"
                        cell_text = "—"

                    td_style = (
                        "padding:2px 4px;border:1px solid #374151;" f"font-size:11px;{cell_style}"
                    )
                    cells_html += f'<td style="{td_style}">{cell_text}</td>'

                header_td_style = (
                    "padding:2px 4px;font-size:10px;color:#94a3b8;"
                    "background:#1e293b;border:1px solid #374151;"
                )
                rows_html += (
                    f'<tr><td colspan="20" style="{header_td_style}">'
                    f"Group {group.group_number}</td></tr>"
                    f"<tr>{cells_html}</tr>"
                )

            buildings_html += f"""
            <div style="margin-right:12px;margin-bottom:8px;">
                <div style="font-size:10px;color:#9ca3af;margin-bottom:2px;">
                    #{bldg.building_number} (Lv {bldg.level}){' [broken]' if bldg.is_broken else ''}
                </div>
                <table style="border-collapse:collapse;">{rows_html}</table>
            </div>"""

        sections_html += f"""
        <div style="margin-bottom:16px;">
            <div style="background:{color};color:#fff;font-size:12px;font-weight:bold;
                        padding:4px 8px;border-radius:4px 4px 0 0;">{label}</div>
            <div style="background:#0f172a;padding:8px;border-radius:0 0 4px 4px;
                        display:flex;flex-wrap:wrap;">{buildings_html}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    background: #030712;
    color: #f9fafb;
    font-family: system-ui, sans-serif;
    padding: 16px;
    margin: 0;
    min-width: 600px;
  }}
  h1 {{
    font-size: 16px;
    margin: 0 0 16px 0;
    color: #f9fafb;
  }}
</style>
</head>
<body>
  <h1>Siege Assignments &mdash; {siege_date}</h1>
  {sections_html}
</body>
</html>"""


def _build_reserves_html(members: list[SiegeMemberWithName], siege_date: str) -> str:
    """Build the reserves/members list HTML string."""
    rows_html = ""
    for m in members:
        day_label = str(m.attack_day) if m.attack_day is not None else "—"
        if m.attack_day == 1:
            day_style = "color:#60a5fa;font-weight:bold;"
        elif m.attack_day == 2:
            day_style = "color:#fb923c;font-weight:bold;"
        else:
            day_style = "color:#6b7280;"

        reserve_label = (
            "Yes" if m.has_reserve_set else ("No" if m.has_reserve_set is False else "—")
        )

        rows_html += f"""
        <tr>
            <td style="padding:4px 8px;border:1px solid #374151;">{m.name}</td>
            <td style="padding:4px 8px;border:1px solid #374151;{day_style}">{day_label}</td>
            <td style="padding:4px 8px;border:1px solid #374151;color:#9ca3af;">{reserve_label}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    background: #030712;
    color: #f9fafb;
    font-family: system-ui, sans-serif;
    padding: 16px;
    margin: 0;
    min-width: 400px;
  }}
  h1 {{
    font-size: 16px;
    margin: 0 0 16px 0;
    color: #f9fafb;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
    font-size: 12px;
  }}
  th {{
    background: #1f2937;
    color: #d1d5db;
    padding: 4px 8px;
    border: 1px solid #374151;
    text-align: left;
    font-weight: 600;
  }}
  tr:nth-child(even) td {{
    background: #111827;
  }}
  tr:nth-child(odd) td {{
    background: #0f172a;
  }}
</style>
</head>
<body>
  <h1>Siege Members &mdash; {siege_date}</h1>
  <table>
    <thead>
      <tr>
        <th>Name</th>
        <th>Attack Day</th>
        <th>Has Reserve Set</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Playwright renderer
# ---------------------------------------------------------------------------


async def _render_html_to_png(html: str) -> bytes:
    """Render an HTML string to PNG bytes using headless Chromium."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page()
        await page.set_content(html)
        await page.wait_for_load_state("networkidle")
        screenshot = await page.screenshot(full_page=True)
        await browser.close()
        return screenshot


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


async def generate_assignments_image(board: BoardResponse, siege_date: str) -> bytes:
    """Render the assignments board as a PNG. Returns raw PNG bytes."""
    html = _build_assignments_html(board, siege_date)
    return await _render_html_to_png(html)


async def generate_reserves_image(members: list[SiegeMemberWithName], siege_date: str) -> bytes:
    """Render the members/reserves list as a PNG. Returns raw PNG bytes."""
    html = _build_reserves_html(members, siege_date)
    return await _render_html_to_png(html)
