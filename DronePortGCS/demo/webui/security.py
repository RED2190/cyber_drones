from __future__ import annotations

import re
from typing import Any, Dict


def _clean_md(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = cleaned.replace("`", "")
    return cleaned.strip()


def _extract_between(text: str, start_marker: str, end_marker: str | None = None) -> str:
    start = text.find(start_marker)
    if start == -1:
        return ""
    start += len(start_marker)
    if end_marker:
        end = text.find(end_marker, start)
        if end != -1:
            return text[start:end].strip()
    return text[start:].strip()


def _parse_md_table(section_text: str) -> Dict[str, Any]:
    lines = [line.strip() for line in section_text.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return {"headers": [], "rows": []}
    headers = [_clean_md(cell) for cell in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        rows.append([_clean_md(cell) for cell in line.strip("|").split("|")])
    return {"headers": headers, "rows": rows}


def _parse_bullets(section_text: str) -> list[str]:
    items = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("* "):
            items.append(_clean_md(stripped[2:]))
        elif stripped.startswith("🔴 "):
            items.append(_clean_md(stripped))
    return items


def _parse_threats(section_text: str) -> list[Dict[str, Any]]:
    threats = []
    parts = section_text.split("### ")
    for part in parts[1:]:
        lines = part.splitlines()
        title = _clean_md(lines[0])
        description = _extract_between(part, "**Описание:**", "**Нарушаемые цели:**")
        violated = _extract_between(part, "**Нарушаемые цели:**", "**Критичность:**")
        criticality = _extract_between(part, "**Критичность:**", "**Контрмеры:**")
        countermeasures = _parse_bullets(_extract_between(part, "**Контрмеры:**", "---"))
        threats.append(
            {
                "title": title,
                "description": _clean_md(description),
                "violated_goals": [line.strip() for line in violated.splitlines() if line.strip()],
                "criticality": _clean_md(criticality),
                "countermeasures": countermeasures,
            }
        )
    return threats


def parse_security_analysis(text: str) -> Dict[str, Any]:
    if not text:
        return {}

    assets_section = _extract_between(text, "### 1.1 Идентификация активов", "### 1.2 Оценка уровня ущерба")
    damage_section = _extract_between(text, "### 1.2 Оценка уровня ущерба", "### 1.3 Приемлемость риска")
    risk_section = _extract_between(text, "### 1.3 Приемлемость риска", "### Вывод по пункту 1")
    conclusion_section = _extract_between(text, "### Вывод по пункту 1", "## Пункт 2.")
    goals_section = _extract_between(text, "### 4.1 Цели безопасности", "# 4.2 Предположения безопасности")
    assumptions_section = _extract_between(text, "# 4.2 Предположения безопасности", "## Пункт 5. Моделирование угроз")
    threats_section = _extract_between(text, "## Пункт 5. Моделирование угроз", "## Пункт 6. Домен доверия")
    trust_section = _extract_between(text, "## Пункт 6. Домен доверия")

    damage_scale_section = _extract_between(damage_section, "Шкала оценки:", "##### Таблица оценки активов НУС")
    damage_assets_section = _extract_between(damage_section, "##### Таблица оценки активов НУС")
    critical_assets_section = _extract_between(
        conclusion_section,
        "Наиболее критичные активы системы:",
        "Их компрометация может привести к:",
    )
    critical_effects_section = _extract_between(conclusion_section, "Их компрометация может привести к:")

    return {
        "assets": _parse_md_table(assets_section),
        "damage_scale": _parse_md_table(damage_scale_section),
        "damage_assets": _parse_md_table(damage_assets_section),
        "risk_acceptance": _parse_md_table(risk_section),
        "critical_assets": _parse_bullets(critical_assets_section),
        "critical_effects": _parse_bullets(critical_effects_section),
        "security_goals": _parse_md_table(goals_section),
        "security_assumptions": _parse_md_table(assumptions_section),
        "threats": _parse_threats(threats_section),
        "trust_domain": _parse_md_table(trust_section),
    }
