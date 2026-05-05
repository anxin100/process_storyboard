"""
license 工具共用：构建未签名字典、规范序列化、文件名清理。
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

PRODUCT_ID = "process_storyboard"
LICENSE_VERSION = 1


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_rfc3339_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def add_months(dt: datetime, months: int) -> datetime:
    y = dt.year
    m = dt.month + months
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1

    if m in (1, 3, 5, 7, 8, 10, 12):
        last_day = 31
    elif m in (4, 6, 9, 11):
        last_day = 30
    else:
        is_leap = (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)
        last_day = 29 if is_leap else 28

    day = min(dt.day, last_day)
    return dt.replace(year=y, month=m, day=day)


def add_years(dt: datetime, years: int) -> datetime:
    try:
        return dt.replace(year=dt.year + years)
    except ValueError:
        return dt.replace(year=dt.year + years, day=28)


@dataclass
class Term:
    kind: str
    count: int


def build_validity(term: Term, not_before: datetime) -> dict:
    if term.kind == "perpetual":
        return {"not_before": to_rfc3339_z(not_before), "is_perpetual": True, "not_after": None}
    if term.kind == "month":
        not_after = add_months(not_before, term.count)
        return {"not_before": to_rfc3339_z(not_before), "is_perpetual": False, "not_after": to_rfc3339_z(not_after)}
    if term.kind == "year":
        not_after = add_years(not_before, term.count)
        return {"not_before": to_rfc3339_z(not_before), "is_perpetual": False, "not_after": to_rfc3339_z(not_after)}
    raise ValueError(f"未知 term：{term.kind}")


def make_license_id(ts: datetime) -> str:
    return f"LIC-{ts.year}-{uuid.uuid4().hex[:8].upper()}"


def sanitize_for_filename(s: str, max_len: int = 96) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f\r\n\t]+', "_", s)
    s = s.strip(" .")
    s = re.sub(r"_+", "_", s)
    if len(s) > max_len:
        s = s[:max_len].rstrip("_")
    return s


def customer_archive_dir_name(customer_name: str, customer_contact: str) -> str:
    """签发留底目录名：客户名@联系方式（段为空则省略对应侧，避免裸 @）。"""
    sn = sanitize_for_filename(customer_name)
    sc = sanitize_for_filename(customer_contact)
    if sn and sc:
        return f"{sn}@{sc}"
    if sn:
        return sn
    if sc:
        return sc
    return "unknown_customer"


def build_unsigned_license_object(
    *,
    term_kind: str,
    term_count: int,
    customer_name: str,
    customer_contact: str,
    machine_ids: List[str],
    license_id: Optional[str] = None,
    issued: Optional[datetime] = None,
) -> Dict[str, Any]:
    issued = issued or now_utc()
    lid = (license_id or "").strip() or make_license_id(issued)
    term = Term(kind=term_kind, count=int(term_count))
    validity = build_validity(term, issued)
    return {
        "license_version": LICENSE_VERSION,
        "product": PRODUCT_ID,
        "license_id": lid,
        "issued_at": to_rfc3339_z(issued),
        "validity": validity,
        "customer": {"name": customer_name, "contact": customer_contact},
        "binding": {"type": "machine", "machine_ids": list(machine_ids)},
        "migration": {"mode": "manual", "note": "需人工换机：请联系授权方签发新 license"},
    }


def canonical_license_bytes(obj: Dict[str, Any]) -> bytes:
    """与客户端 verify 一致：排序键 + 无签名时的 canonical JSON。"""
    if "signature" in obj:
        raise ValueError("canonical_license_bytes 要求对象不含 signature")
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
