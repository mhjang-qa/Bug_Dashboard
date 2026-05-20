#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
OUT_FILE = "defect_dashboard_embed.html"
NOTION_VERSION = "2022-06-28"
DEFAULT_DEFECT_DB_ID = "21473fbd1951800d8321fc2e34c2548e"
DEFAULT_REPO_URL = "https://github.com/mhjang-qa/Bug_Dashboard.git"
DEFAULT_BRANCH = "main"

FIELD_MAP: dict[str, list[str]] = {
    "title": ["결함 요약", "제목", "Name", "Title", "Summary", "Bug"],
    "status": ["상태", "Status", "처리상태"],
    "severity": ["심각도", "Severity", "등급"],
    "priority": ["우선순위", "Priority"],
    "assignee": ["담당자", "Assignee", "Owner", "작업자"],
    "version": ["목표버전", "버전", "Version", "앱버전", "App Version", "Web Version"],
    "os": ["OS", "플랫폼", "Platform", "환경", "디바이스"],
    "created_at": ["등록일", "생성 일시", "Created", "Date", "작성일", "created_time"],
    "fixed_at": ["수정완료일", "수정 완료일", "Fixed Date", "Resolved Date"],
    "closed_at": ["종료일", "완료일", "Closed Date", "Done Date"],
    "id": ["ID", "결함 ID", "Bug ID"],
}

FUNNEL_STAGES = ["등록", "검토", "배정", "진행중", "수정완료", "QA확인", "종료"]
SEVERITY_ORDER = ["Blocker", "Critical", "Major", "Minor", "Trivial", "미지정"]
PRIORITY_ORDER = ["P0", "P1", "P2", "P3", "High", "Medium", "Low", "미지정"]
OS_ORDER = ["AOS", "iOS", "Web", "공통", "미지정"]


class StepError(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"[defect-dashboard] {message}", flush=True)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_env() -> None:
    for path in (ROOT_DIR / ".env", SCRIPT_DIR / ".env", ROOT_DIR / "notion_hit" / ".env"):
        load_env_file(path)


def env_first(names: list[str], default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def database_id() -> str:
    return env_first(
        [
            "NOTION_DEFECT_DB_ID",
            "DEFECT_NOTION_DB_ID",
            "NOTION_QA_DEFECT_DB_ID",
            "NOTION_DATABASE_ID",
        ],
        DEFAULT_DEFECT_DB_ID,
    )


def notion_request(path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    token = os.getenv("NOTION_TOKEN", "").strip()
    if not token:
        raise StepError("NOTION_TOKEN is required.")

    data = None
    method = "GET"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"

    request = urllib.request.Request(
        f"https://api.notion.com/v1{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": os.getenv("NOTION_VERSION", NOTION_VERSION),
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise StepError(f"Notion API error {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise StepError(f"Notion API request failed: {exc.reason}") from exc


def fetch_pages() -> list[dict[str, Any]]:
    db_id = database_id()
    log(f"query Notion database: {db_id}")
    pages: list[dict[str, Any]] = []
    payload: dict[str, Any] = {"page_size": 100}
    page_no = 1
    while True:
        data = notion_request(f"/databases/{db_id}/query", payload)
        chunk = data.get("results", [])
        pages.extend(chunk)
        log(f"fetched page {page_no}: {len(chunk)} rows, total {len(pages)}")
        if not data.get("has_more"):
            return pages
        payload["start_cursor"] = data.get("next_cursor")
        page_no += 1


def plain_text(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    prop_type = prop.get("type")
    value = prop.get(prop_type) if prop_type else None
    if prop_type in ("title", "rich_text"):
        return "".join(part.get("plain_text", "") for part in value or [])
    if prop_type in ("select", "status"):
        return (value or {}).get("name", "")
    if prop_type == "multi_select":
        return ", ".join(item.get("name", "") for item in value or [] if item.get("name"))
    if prop_type == "people":
        names = [item.get("name") or item.get("person", {}).get("email") for item in value or []]
        return ", ".join(name for name in names if name)
    if prop_type == "unique_id":
        prefix = value.get("prefix") or ""
        number = value.get("number")
        return f"{prefix}-{number}" if prefix and number is not None else str(number or "")
    if prop_type in ("created_time", "last_edited_time"):
        return value or ""
    if prop_type == "date":
        return (value or {}).get("start", "")
    if prop_type == "number":
        return "" if value is None else str(value)
    if prop_type == "formula":
        formula_type = (value or {}).get("type")
        formula_value = (value or {}).get(formula_type)
        if formula_type == "date":
            return (formula_value or {}).get("start", "")
        if formula_value is None:
            return ""
        return str(formula_value)
    if prop_type == "rollup":
        rollup = value or {}
        if rollup.get("type") == "array":
            return ", ".join(plain_text(item) for item in rollup.get("array", []) if plain_text(item))
        return str(rollup.get(rollup.get("type"), "") or "")
    if prop_type == "url":
        return value or ""
    return ""


def first_value(properties: dict[str, Any], key: str) -> str:
    for name in FIELD_MAP[key]:
        if name == "created_time":
            continue
        if name in properties:
            value = plain_text(properties.get(name))
            if value:
                return value
    return ""


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone()
    except ValueError:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc).astimezone()
        except ValueError:
            return None


def date_key(value: str | None) -> str:
    parsed = parse_dt(value)
    return parsed.date().isoformat() if parsed else ""


def normalize_status(status: str) -> str:
    text = (status or "").strip()
    compact = re.sub(r"\s+", "", text).lower()
    if any(token in compact for token in ["qa확인", "qa검증", "qaverification", "회귀"]):
        return "QA확인"
    if any(token in compact for token in ["수정완료", "resolved", "fixed", "dev배포", "배포-완료"]):
        return "수정완료"
    if any(token in compact for token in ["종료", "완료", "done", "closed", "결함아님", "notanissue"]):
        return "종료"
    if any(token in compact for token in ["진행", "inprogress", "working"]):
        return "진행중"
    if any(token in compact for token in ["배정", "assigned"]):
        return "배정"
    if any(token in compact for token in ["검토", "review", "triage"]):
        return "검토"
    if any(token in compact for token in ["등록", "registered", "new", "open", "reopen"]):
        return "등록"
    return text or "미지정"


def normalize_severity(severity: str) -> str:
    text = (severity or "").strip()
    lowered = text.lower()
    if "blocker" in lowered:
        return "Blocker"
    if "critical" in lowered or "치명" in text:
        return "Critical"
    if "major" in lowered or "주요" in text:
        return "Major"
    if "minor" in lowered or "경미" in text:
        return "Minor"
    if "trivial" in lowered:
        return "Trivial"
    return text or "미지정"


def normalize_os(value: str) -> str:
    text = (value or "").strip()
    upper = text.upper()
    if "AOS" in upper or "ANDROID" in upper:
        return "AOS"
    if "IOS" in upper or "IPHONE" in upper:
        return "iOS"
    if "WEB" in upper or "웹" in text:
        return "Web"
    if "공통" in text or "COMMON" in upper:
        return "공통"
    return text or "미지정"


def normalize_priority(value: str) -> str:
    text = (value or "").strip()
    upper = text.upper()
    for priority in ("P0", "P1", "P2", "P3"):
        if priority in upper:
            return priority
    if "HIGH" in upper or "높" in text:
        return "High"
    if "MEDIUM" in upper or "보통" in text:
        return "Medium"
    if "LOW" in upper or "낮" in text:
        return "Low"
    return text or "미지정"


def normalize_page(page: dict[str, Any]) -> dict[str, Any]:
    properties = page.get("properties", {})
    created = first_value(properties, "created_at") or page.get("created_time", "")
    status_raw = first_value(properties, "status")
    status_stage = normalize_status(status_raw)
    fixed_at = first_value(properties, "fixed_at")
    closed_at = first_value(properties, "closed_at")
    if not fixed_at and status_stage in {"수정완료", "QA확인", "종료"}:
        fixed_at = page.get("last_edited_time", "")
    if not closed_at and status_stage == "종료":
        closed_at = page.get("last_edited_time", "")

    return {
        "id": first_value(properties, "id") or page.get("id", ""),
        "title": first_value(properties, "title") or "제목 없음",
        "status": status_raw or "미지정",
        "stage": status_stage if status_stage in FUNNEL_STAGES else "등록",
        "severity": normalize_severity(first_value(properties, "severity")),
        "priority": normalize_priority(first_value(properties, "priority")),
        "assignee": first_value(properties, "assignee") or "미지정",
        "version": first_value(properties, "version") or "미지정",
        "os": normalize_os(first_value(properties, "os")),
        "createdAt": created,
        "createdDate": date_key(created),
        "fixedAt": fixed_at,
        "fixedDate": date_key(fixed_at),
        "closedAt": closed_at,
        "closedDate": date_key(closed_at),
        "url": page.get("url", ""),
        "lastEditedAt": page.get("last_edited_time", ""),
    }


def ordered_counts(counter: Counter[str], preferred: list[str] | None = None) -> list[dict[str, Any]]:
    items: list[tuple[str, int]] = []
    seen: set[str] = set()
    for key in preferred or []:
        if key in counter:
            items.append((key, counter[key]))
            seen.add(key)
    for key, count in counter.most_common():
        if key not in seen:
            items.append((key, count))
    return [{"label": key, "count": int(count)} for key, count in items]


def daily_range(days: int) -> list[date]:
    today = datetime.now().date()
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def build_daily(rows: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
    created = Counter(row["createdDate"] for row in rows if row["createdDate"])
    fixed = Counter(row["fixedDate"] for row in rows if row["fixedDate"])
    closed = Counter(row["closedDate"] for row in rows if row["closedDate"])
    result: list[dict[str, Any]] = []
    previous_new = 0
    for day in daily_range(days):
        key = day.isoformat()
        new_count = int(created[key])
        result.append(
            {
                "date": key,
                "new": new_count,
                "fixed": int(fixed[key]),
                "closed": int(closed[key]),
                "deltaNew": new_count - previous_new,
            }
        )
        previous_new = new_count
    return result


def build_versions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["version"]].append(row)
    versions: list[dict[str, Any]] = []
    for version, items in grouped.items():
        total = len(items)
        critical_major = sum(1 for item in items if item["severity"] in {"Blocker", "Critical", "Major"})
        done = sum(1 for item in items if item["stage"] in {"수정완료", "QA확인", "종료"})
        versions.append(
            {
                "version": version,
                "total": total,
                "criticalMajor": critical_major,
                "doneRate": round(done / total * 100, 1) if total else 0,
                "status": ordered_counts(Counter(item["stage"] for item in items), FUNNEL_STAGES),
                "severity": ordered_counts(Counter(item["severity"] for item in items), SEVERITY_ORDER),
                "priority": ordered_counts(Counter(item["priority"] for item in items), PRIORITY_ORDER),
            }
        )
    return sorted(versions, key=lambda item: (-item["total"], item["version"]))[:12]


def build_payload(rows: list[dict[str, Any]], days: int) -> dict[str, Any]:
    today = datetime.now().date().isoformat()
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
    total = len(rows)
    stage_counts = Counter(row["stage"] for row in rows)
    today_new = sum(1 for row in rows if row["createdDate"] == today)
    yesterday_new = sum(1 for row in rows if row["createdDate"] == yesterday)
    funnel = []
    for index, stage in enumerate(FUNNEL_STAGES):
        count = int(stage_counts[stage])
        width = max(42, 100 - index * 7)
        funnel.append(
            {
                "stage": stage,
                "count": count,
                "rate": round(count / total * 100, 1) if total else 0,
                "width": width,
            }
        )

    recent = sorted(rows, key=lambda item: item.get("createdAt") or "", reverse=True)[:10]
    daily = build_daily(rows, max(days, 30))
    heatmap = daily[-90:]
    return {
        "generatedAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "days": days,
        "summary": {
            "total": total,
            "new": int(stage_counts["등록"]),
            "inProgress": int(stage_counts["진행중"]),
            "fixed": int(stage_counts["수정완료"]),
            "closed": int(stage_counts["종료"]),
            "todayNew": today_new,
            "newDelta": today_new - yesterday_new,
        },
        "funnel": funnel,
        "daily": daily,
        "versions": build_versions(rows),
        "selectedVersion": "ALL",
        "distributions": {
            "ALL": {
                "status": ordered_counts(Counter(row["stage"] for row in rows), FUNNEL_STAGES),
                "severity": ordered_counts(Counter(row["severity"] for row in rows), SEVERITY_ORDER),
                "priority": ordered_counts(Counter(row["priority"] for row in rows), PRIORITY_ORDER),
            }
        },
        "heatmap": heatmap,
        "recent": recent,
    }


def build_html(payload: dict[str, Any]) -> str:
    data_json = json.dumps(payload, ensure_ascii=False, indent=2).replace("</script", "<\\/script")
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>결함 대시보드</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f7fb;
      --panel: #ffffff;
      --panel-soft: #f8fbff;
      --line: rgba(31, 41, 55, .10);
      --text: #172033;
      --muted: #5f6b7e;
      --blue: #1d86f2;
      --green: #1ea97c;
      --yellow: #d99a00;
      --red: #d14a61;
      --violet: #7b61ff;
      --shadow: 0 12px 30px rgba(17, 24, 39, .07);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }}
    .wrap {{ width: 100%; min-height: 100vh; padding: 24px; }}
    header {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 16px;
      align-items: start;
      margin-bottom: 18px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 26px; font-weight: 760; }}
    .lead {{ margin: 0; max-width: 980px; color: var(--muted); font-size: 14px; line-height: 1.55; }}
    .notice {{ margin-top: 8px; color: var(--muted); font-size: 12px; }}
    .stamp {{ text-align: right; color: var(--muted); font-size: 12px; white-space: nowrap; }}
    .tabs {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 18px; }}
    .tab, .range-btn {{
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--muted);
      padding: 9px 13px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 13px;
    }}
    .tab.active, .range-btn.active {{ color: var(--text); border-color: rgba(29, 134, 242, .45); background: rgba(29, 134, 242, .08); }}
    .panel-head {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }}
    .panel-head h2 {{ margin: 0; }}
    .range-controls {{ display: flex; gap: 6px; }}
    .range-btn {{ padding: 7px 10px; font-size: 12px; }}
    .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 18px; }}
    .card, .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; box-shadow: var(--shadow); }}
    .card {{ padding: 14px; min-height: 94px; }}
    .card span {{ display: block; color: var(--muted); font-size: 12px; margin-bottom: 9px; }}
    .card strong {{ display: block; font-size: 29px; line-height: 1; }}
    .card em {{ display: block; margin-top: 8px; color: var(--muted); font-size: 12px; font-style: normal; }}
    .up {{ color: var(--red) !important; }}
    .down {{ color: var(--green) !important; }}
    .grid {{ display: grid; grid-template-columns: minmax(320px, .95fr) minmax(420px, 1.45fr); gap: 14px; }}
    .grid.three {{ grid-template-columns: repeat(3, minmax(180px, 1fr)); gap: 10px; }}
    .panel {{ padding: 16px; min-width: 0; }}
    .panel h2 {{ margin: 0 0 12px; font-size: 16px; font-weight: 720; }}
    .subtle {{ color: var(--muted); font-size: 12px; }}
    .view {{ display: none; }}
    .view.active {{ display: block; }}
    .funnel {{ display: grid; gap: 8px; align-items: center; justify-items: center; padding: 4px 0; }}
    .funnel-row {{
      display: grid;
      grid-template-columns: 86px 1fr 76px;
      align-items: center;
      width: 100%;
      gap: 10px;
      color: var(--text);
      font-size: 13px;
    }}
    .funnel-bar {{
      height: 38px;
      border-radius: 6px;
      background: linear-gradient(90deg, rgba(29,134,242,.92), rgba(30,169,124,.88));
      display: flex;
      align-items: center;
      justify-content: center;
      color: #ffffff;
      font-weight: 800;
      min-width: 72px;
    }}
    .chart {{ height: 270px; display: flex; align-items: end; gap: 8px; padding-top: 8px; border-bottom: 1px solid var(--line); overflow-x: auto; overflow-y: hidden; }}
    .day {{ flex: 1; min-width: 8px; display: grid; grid-template-rows: 1fr auto; gap: 6px; height: 100%; }}
    .bars {{ display: flex; gap: 3px; align-items: end; height: 100%; }}
    .bar {{ flex: 1; min-height: 2px; border-radius: 3px 3px 0 0; }}
    .bar.new {{ background: var(--blue); }}
    .bar.fixed {{ background: var(--yellow); }}
    .bar.closed {{ background: var(--green); }}
    .label {{ color: var(--muted); font-size: 10px; text-align: center; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; color: var(--muted); font-size: 12px; }}
    .dot {{ width: 9px; height: 9px; display: inline-block; border-radius: 50%; margin-right: 5px; }}
    .version-list, .dist-list {{ display: grid; gap: 9px; }}
    .version-list {{ max-height: 480px; overflow: auto; padding-right: 4px; }}
    .version-item {{
      display: grid;
      grid-template-columns: minmax(110px, 170px) 1fr 68px;
      gap: 10px;
      align-items: center;
      width: 100%;
      border: 1px solid var(--line);
      background: var(--panel-soft);
      border-radius: 8px;
      padding: 10px;
      text-align: left;
      cursor: pointer;
    }}
    .version-item.active {{ border-color: rgba(29, 134, 242, .45); box-shadow: 0 0 0 2px rgba(29, 134, 242, .08) inset; }}
    .row {{ display: grid; grid-template-columns: minmax(120px, 160px) 1fr 62px; gap: 10px; align-items: center; font-size: 13px; }}
    .track {{ height: 10px; background: rgba(148,163,184,.16); border-radius: 999px; overflow: hidden; }}
    .fill {{ height: 100%; background: linear-gradient(90deg, var(--blue), var(--green)); }}
    .meta {{ color: var(--muted); font-size: 12px; }}
    .heatmap-wrap {{ display: grid; gap: 12px; }}
    .heatmap {{ display: grid; grid-template-columns: repeat(30, minmax(10px, 1fr)); gap: 4px; }}
    .tile {{ aspect-ratio: 1; border-radius: 4px; background: #e5edf7; border: 1px solid rgba(31,41,55,.06); }}
    .tile[data-level="1"] {{ background: rgba(29,134,242,.22); }}
    .tile[data-level="2"] {{ background: rgba(29,134,242,.40); }}
    .tile[data-level="3"] {{ background: rgba(29,134,242,.60); }}
    .tile[data-level="4"] {{ background: rgba(30,169,124,.80); }}
    .heatmap-scale {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; color: var(--muted); font-size: 12px; }}
    .scale-swatch {{ width: 14px; height: 14px; border-radius: 4px; border: 1px solid rgba(31,41,55,.06); display: inline-block; margin-right: 6px; vertical-align: middle; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ padding: 11px 9px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; font-weight: 650; }}
    td a {{ color: var(--text); text-decoration: none; }}
    .recent-row {{ cursor: pointer; }}
    .recent-row:hover {{ background: rgba(29, 134, 242, .05); }}
    .recent-row:focus {{ outline: 2px solid rgba(29, 134, 242, .35); outline-offset: -2px; }}
    .pill {{ display: inline-flex; max-width: 150px; padding: 4px 8px; border-radius: 999px; background: rgba(29,134,242,.10); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .empty {{ color: var(--muted); padding: 20px; text-align: center; border: 1px dashed var(--line); border-radius: 8px; }}
    .table-wrap {{ overflow-x: auto; }}
    @media (max-width: 1100px) {{
      .grid, .grid.three {{ grid-template-columns: 1fr; }}
      .summary {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .version-list {{ max-height: none; }}
      header {{ grid-template-columns: 1fr; }}
      .stamp {{ text-align: left; }}
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        color-scheme: dark;
        --bg: #0f172a;
        --panel: #111c33;
        --panel-soft: #16233d;
        --line: rgba(148, 163, 184, .18);
        --text: #e7eef9;
        --muted: #9db0c8;
        --blue: #61b7ff;
        --green: #47d19b;
        --yellow: #ffd166;
        --red: #ff7a8a;
        --violet: #a78bfa;
        --shadow: 0 14px 32px rgba(0, 0, 0, .22);
      }}
      .tile {{ background: #172036; border-color: rgba(148,163,184,.10); }}
      .tab, .range-btn, .version-item {{ background: #0b1220; }}
      .version-item.active {{ border-color: rgba(97, 183, 255, .45); box-shadow: 0 0 0 2px rgba(97, 183, 255, .08) inset; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div>
        <h1>결함 대시보드</h1>
        <p class="lead">본 대시보드는 결함 등록, 검토, 배정, 수정 및 종료 현황을 기반으로 서비스 품질 흐름을 시각화한 내부 관리자 전용 화면입니다.</p>
        <div class="notice">승인된 담당자 외 접근·열람·수정·공유를 제한하며, 모든 결함 정보 및 이력 데이터는 내부 품질 관리 목적으로만 사용됩니다.</div>
      </div>
      <div class="stamp" id="stamp"></div>
    </header>
    <nav class="tabs" aria-label="대시보드 탭">
      <button class="tab active" data-view="overview">흐름 요약</button>
      <button class="tab" data-view="trend">일별 추이</button>
      <button class="tab" data-view="version">버전/분포</button>
      <button class="tab" data-view="recent">최근 결함</button>
    </nav>
    <section class="summary" id="summary"></section>
    <main>
      <section class="view active" id="overview">
        <div class="grid">
          <article class="panel"><h2>결함 처리 퍼널</h2><div class="funnel" id="funnel"></div></article>
          <article class="panel">
            <h2>최근 30일 등록 히트맵</h2>
            <div class="heatmap-wrap">
              <div class="heatmap" id="heatmap"></div>
              <div class="heatmap-scale" aria-label="히트맵 범례">
                <span><i class="scale-swatch" style="background:rgba(29,134,242,.12)"></i>낮음</span>
                <span><i class="scale-swatch" style="background:rgba(29,134,242,.32)"></i>보통</span>
                <span><i class="scale-swatch" style="background:rgba(29,134,242,.58)"></i>높음</span>
                <span><i class="scale-swatch" style="background:rgba(30,169,124,.80)"></i>최고</span>
              </div>
            </div>
          </article>
        </div>
      </section>
      <section class="view" id="trend">
        <article class="panel"><div class="panel-head"><h2>일별 결함 변동 추이</h2><div class="range-controls"><button class="range-btn" data-days="7">7일</button><button class="range-btn" data-days="14">14일</button><button class="range-btn active" data-days="30">30일</button></div></div><div class="chart" id="dailyChart"></div><div class="legend"><span><i class="dot" style="background:var(--blue)"></i>신규</span><span><i class="dot" style="background:var(--yellow)"></i>수정완료</span><span><i class="dot" style="background:var(--green)"></i>종료</span></div><div class="meta" id="trendNote" style="margin-top:10px"></div></article>
      </section>
      <section class="view" id="version">
        <div class="grid">
          <article class="panel"><div class="panel-head"><h2>버전별 결함 추이</h2><div class="subtle" id="selectedVersionLabel">전체</div></div><div class="version-list" id="versions"></div></article>
          <article class="panel"><div class="panel-head"><h2>상태/심각도/우선순위 분포</h2><div class="subtle" id="distributionScope">전체 기준</div></div><div class="grid three" id="distributions"></div></article>
        </div>
      </section>
      <section class="view" id="recent">
        <article class="panel"><h2>최근 등록 결함 10건</h2><div class="table-wrap" id="recentList"></div></article>
      </section>
    </main>
  </div>
  <script id="dashboard-data" type="application/json">{data_json}</script>
  <script>
    const DATA = JSON.parse(document.getElementById("dashboard-data").textContent);
    const $ = (id) => document.getElementById(id);
    const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[c]));
    const pct = (n) => `${{Number(n || 0).toFixed(1)}}%`;
    let selectedVersion = DATA.selectedVersion || "ALL";
    $("stamp").textContent = `생성: ${{DATA.generatedAt.replace("T", " ")}} · 기준 ${{DATA.days}}일`;

    function renderSummary() {{
      const s = DATA.summary;
      const cards = [
        ["전체 결함", s.total, "Notion DB 전체 조회 기준"],
        ["신규 등록", s.new, "등록 단계"],
        ["진행중", s.inProgress, "개발/수정 진행"],
        ["수정완료", s.fixed, "QA 확인 전후"],
        ["종료/완료", s.closed, "종료 단계"],
        ["금일 신규", s.todayNew, "오늘 등록 수"],
        ["전일 대비", s.newDelta, s.newDelta > 0 ? "증가" : s.newDelta < 0 ? "감소" : "변동 없음"],
      ];
      $("summary").innerHTML = cards.map(([label, value, note]) => `
        <article class="card"><span>${{esc(label)}}</span><strong>${{esc(value)}}</strong><em class="${{label === "전일 대비" ? (value > 0 ? "up" : value < 0 ? "down" : "") : ""}}">${{esc(note)}}</em></article>
      `).join("");
    }}

    function renderFunnel() {{
      const max = Math.max(...DATA.funnel.map((d) => d.count), 1);
      $("funnel").innerHTML = DATA.funnel.map((d) => `
        <div class="funnel-row">
          <div>${{esc(d.stage)}}</div>
          <div class="funnel-bar" style="width:${{d.width}}%; opacity:${{0.45 + d.count / max * 0.55}}">${{d.count}}건</div>
          <div class="meta">${{pct(d.rate)}}</div>
        </div>
      `).join("");
    }}

    function renderDaily(days = DATA.days) {{
      const rows = DATA.daily.slice(-days);
      const max = Math.max(...rows.flatMap((d) => [d.new, d.fixed, d.closed]), 1);
      $("dailyChart").innerHTML = rows.map((d) => `
        <div class="day" title="${{d.date}} 신규 ${{d.new}}, 수정완료 ${{d.fixed}}, 종료 ${{d.closed}}">
          <div class="bars">
            <div class="bar new" style="height:${{Math.max(2, d.new / max * 100)}}%"></div>
            <div class="bar fixed" style="height:${{Math.max(2, d.fixed / max * 100)}}%"></div>
            <div class="bar closed" style="height:${{Math.max(2, d.closed / max * 100)}}%"></div>
          </div>
          <div class="label">${{d.date.slice(5)}}</div>
        </div>
      `).join("");
      const last = rows[rows.length - 1] || {{new:0, deltaNew:0}};
      const direction = last.deltaNew > 0 ? "증가" : last.deltaNew < 0 ? "감소" : "변동 없음";
      $("trendNote").textContent = `최근일 신규 등록 ${{last.new}}건, 전일 대비 ${{Math.abs(last.deltaNew)}}건 ${{direction}}`;
    }}

    function renderHeatmap() {{
      const max = Math.max(...DATA.heatmap.map((d) => d.new), 1);
      $("heatmap").innerHTML = DATA.heatmap.map((d) => {{
        const level = d.new === 0 ? 0 : Math.min(4, Math.ceil(d.new / max * 4));
        return `<div class="tile" data-level="${{level}}" title="${{d.date}} 등록 ${{d.new}}건"></div>`;
      }}).join("");
    }}

    function renderVersions() {{
      const max = Math.max(...DATA.versions.map((d) => d.total), 1);
      const allItem = {{
        version: "ALL",
        label: "전체",
        total: DATA.summary.total,
        criticalMajor: DATA.versions.reduce((sum, item) => sum + (item.criticalMajor || 0), 0),
        doneRate: DATA.summary.total ? Math.round((DATA.summary.closed / DATA.summary.total) * 1000) / 10 : 0,
      }};
      const items = [allItem, ...DATA.versions];
      $("versions").innerHTML = items.length ? items.map((d) => `
        <button class="version-item ${{selectedVersion === d.version ? "active" : ""}}" data-version="${{esc(d.version)}}">
          <div><strong>${{esc(d.version === "ALL" ? d.label : d.version)}}</strong><div class="meta">Major/Critical ${{d.criticalMajor}}건 · 완료율 ${{pct(d.doneRate)}}</div></div>
          <div class="track"><div class="fill" style="width:${{Math.max(8, d.total / max * 100)}}%"></div></div>
          <div>${{d.total}}건</div>
        </button>
      `).join("") : `<div class="empty">표시할 버전 데이터가 없습니다.</div>`;
      document.querySelectorAll(".version-item").forEach((button) => {{
        button.addEventListener("click", () => {{
          selectedVersion = button.dataset.version || "ALL";
          renderVersions();
          renderDistributions();
        }});
      }});
    }}

    function renderDistBox(title, rows) {{
      const max = Math.max(...rows.map((d) => d.count), 1);
      return `<div class="dist-list"><h2>${{esc(title)}}</h2>${{rows.map((d) => `
        <div class="row" style="grid-template-columns:90px 1fr 42px">
          <div class="meta">${{esc(d.label)}}</div><div class="track"><div class="fill" style="width:${{d.count / max * 100}}%"></div></div><div>${{d.count}}</div>
        </div>`).join("")}}</div>`;
    }}

    function renderDistributions() {{
      const version = selectedVersion === "ALL" ? null : DATA.versions.find((item) => item.version === selectedVersion);
      const d = version || DATA.distributions.ALL;
      $("selectedVersionLabel").textContent = version ? version.version : "전체";
      $("distributionScope").textContent = version ? `${{version.version}} 기준` : "전체 기준";
      $("distributions").innerHTML = [
        renderDistBox("상태", d.status),
        renderDistBox("심각도", d.severity),
        renderDistBox("우선순위", d.priority),
      ].join("");
    }}

    function renderRecent() {{
      if (!DATA.recent.length) {{
        $("recentList").innerHTML = `<div class="empty">최근 결함 데이터가 없습니다.</div>`;
        return;
      }}
      $("recentList").innerHTML = `<table><thead><tr><th>제목</th><th>상태</th><th>심각도</th><th>담당자</th><th>등록일</th><th>버전</th></tr></thead><tbody>${{DATA.recent.map((r) => `
        <tr class="recent-row" data-url="${{esc(r.url)}}" tabindex="0" role="link" aria-label="${{esc(r.title)}} Notion에서 열기">
          <td><a href="${{esc(r.url)}}" target="_blank" rel="noreferrer" tabindex="-1">${{esc(r.title)}}</a></td>
          <td><span class="pill">${{esc(r.status)}}</span></td>
          <td>${{esc(r.severity)}}</td>
          <td>${{esc(r.assignee)}}</td>
          <td>${{esc(r.createdDate || r.createdAt)}}</td>
          <td>${{esc(r.version)}}</td>
        </tr>`).join("")}}</tbody></table>`;
      document.querySelectorAll(".recent-row").forEach((row) => {{
        const open = () => {{
          const url = row.dataset.url;
          if (url) window.open(url, "_blank", "noopener,noreferrer");
        }};
        row.addEventListener("click", open);
        row.addEventListener("keydown", (event) => {{
          if (event.key === "Enter" || event.key === " ") {{
            event.preventDefault();
            open();
          }}
        }});
      }});
    }}

    document.querySelectorAll(".tab").forEach((button) => {{
      button.addEventListener("click", () => {{
        document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item === button));
        document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === button.dataset.view));
      }});
    }});

    document.querySelectorAll(".range-btn").forEach((button) => {{
      button.classList.toggle("active", Number(button.dataset.days) === DATA.days);
      button.addEventListener("click", () => {{
        document.querySelectorAll(".range-btn").forEach((item) => item.classList.toggle("active", item === button));
        renderDaily(Number(button.dataset.days));
      }});
    }});

    renderSummary();
    renderFunnel();
    renderDaily();
    renderHeatmap();
    renderVersions();
    renderDistributions();
    renderRecent();
  </script>
</body>
</html>
"""


def run_git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise StepError(f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result


def ensure_publish_repo(repo_url: str, publish_dir: Path, branch: str) -> None:
    publish_dir.parent.mkdir(parents=True, exist_ok=True)
    if not (publish_dir / ".git").exists():
        if publish_dir.exists() and any(publish_dir.iterdir()):
            raise StepError(f"{publish_dir} exists but is not an empty git repository.")
        run_git(["clone", repo_url, str(publish_dir)], cwd=publish_dir.parent)
    run_git(["config", "user.name", "Defect Dashboard Bot"], cwd=publish_dir)
    run_git(["config", "user.email", "defect-dashboard@users.noreply.github.com"], cwd=publish_dir)
    branch_check = run_git(["rev-parse", "--verify", branch], cwd=publish_dir, check=False)
    if branch_check.returncode == 0:
        run_git(["checkout", branch], cwd=publish_dir)
        run_git(["pull", "--ff-only", "origin", branch], cwd=publish_dir, check=False)
    else:
        run_git(["checkout", "-B", branch], cwd=publish_dir)


def publish_html(output_path: Path) -> bool:
    repo_url = os.getenv("DEFECT_DASHBOARD_REPO_URL", DEFAULT_REPO_URL).strip()
    if not repo_url:
        log("publish skipped: DEFECT_DASHBOARD_REPO_URL is not set")
        return False
    branch = os.getenv("DEFECT_DASHBOARD_BRANCH", DEFAULT_BRANCH).strip() or DEFAULT_BRANCH
    publish_dir = Path(os.getenv("DEFECT_DASHBOARD_PUBLISH_DIR", str(SCRIPT_DIR / ".publish" / "defect-dashboard")))
    ensure_publish_repo(repo_url, publish_dir, branch)
    shutil.copy2(output_path, publish_dir / output_path.name)
    run_git(["add", "-A"], cwd=publish_dir)
    diff = run_git(["diff", "--cached", "--quiet"], cwd=publish_dir, check=False)
    if diff.returncode == 0:
        log("no GitHub changes to publish")
        return False
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    run_git(["commit", "-m", f"Update defect dashboard {timestamp}"], cwd=publish_dir)
    run_git(["push", "-u", "origin", branch], cwd=publish_dir)
    log(f"published to {repo_url}")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Notion defect dashboard embed HTML.")
    parser.add_argument("--output", default=OUT_FILE, help="Output HTML file name or path.")
    parser.add_argument("--days", type=int, default=30, choices=[7, 14, 30], help="Default trend window.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--publish", dest="publish", action="store_true", help="Commit/push to GitHub Pages repo if configured.")
    group.add_argument("--no-publish", dest="publish", action="store_false", help="Generate locally only.")
    parser.set_defaults(publish=True)
    return parser.parse_args()


def main() -> int:
    load_env()
    args = parse_args()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = SCRIPT_DIR / output_path

    pages = fetch_pages()
    rows = [normalize_page(page) for page in pages]
    payload = build_payload(rows, args.days)
    output_path.write_text(build_html(payload), encoding="utf-8")
    log(f"generated {output_path} with {len(rows)} rows")
    published = publish_html(output_path) if args.publish else False
    summary = {
        "skipped": False,
        "rows": len(rows),
        "output": str(output_path),
        "published": published,
        "generatedAt": payload["generatedAt"],
        "summary": payload["summary"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[defect-dashboard] failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
