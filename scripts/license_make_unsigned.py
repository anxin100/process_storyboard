"""
生成未签名的 license_unsigned.json（离线授权）。

示例：
  # 永久
  python scripts/license_make_unsigned.py \
    --term perpetual \
    --customer-name "客户A" \
    --customer-contact "a@example.com" \
    --machine-id "MID-XXXX" \
    --out scripts/license_unsigned.json

  # 年付 1 年
  python scripts/license_make_unsigned.py \
    --term year --count 1 \
    --customer-name "客户A" \
    --customer-contact "a@example.com" \
    --machine-id "MID-XXXX" \
    --out scripts/license_unsigned.json

  # 月付 3 个月 + 绑定两台
  python scripts/license_make_unsigned.py \
    --term month --count 3 \
    --customer-name "客户A" \
    --customer-contact "a@example.com" \
    --machine-id "MID-1" --machine-id "MID-2" \
    --out scripts/license_unsigned.json
"""

from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


PRODUCT_ID = "process_storyboard"
LICENSE_VERSION = 1


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_rfc3339_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def add_months(dt: datetime, months: int) -> datetime:
    # 纯标准库实现：按年月滚动，日超出月末则截到月末
    y = dt.year
    m = dt.month + months
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1

    # 计算目标月最后一天
    if m in (1, 3, 5, 7, 8, 10, 12):
        last_day = 31
    elif m in (4, 6, 9, 11):
        last_day = 30
    else:
        # Feb
        is_leap = (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)
        last_day = 29 if is_leap else 28

    day = min(dt.day, last_day)
    return dt.replace(year=y, month=m, day=day)


def add_years(dt: datetime, years: int) -> datetime:
    # 注意 2/29
    try:
        return dt.replace(year=dt.year + years)
    except ValueError:
        # 2/29 -> 2/28
        return dt.replace(year=dt.year + years, day=28)


@dataclass
class Term:
    kind: str  # perpetual | month | year
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
    raise SystemExit(f"未知 term：{term.kind}")


def make_license_id(ts: datetime) -> str:
    # LIC-YYYY-8位随机（不保证严格递增，但足够唯一）
    return f"LIC-{ts.year}-{uuid.uuid4().hex[:8].upper()}"


def main() -> int:
    p = argparse.ArgumentParser(description="Generate unsigned license JSON")
    p.add_argument("--term", choices=["perpetual", "month", "year"], required=True, help="授权类型：永久/月付/年付")
    p.add_argument("--count", type=int, default=1, help="月付/年付的数量（默认 1）")
    p.add_argument("--customer-name", required=True, help="客户名称")
    p.add_argument("--customer-contact", default="", help="客户联系方式（邮箱/手机号等）")
    p.add_argument("--machine-id", action="append", default=[], help="绑定机器码 MID-...（可多次传入）")
    p.add_argument("--license-id", default="", help="自定义 license_id（不传则自动生成）")
    p.add_argument("--out", default="scripts/license_unsigned.json", help="输出路径（默认 scripts/license_unsigned.json）")
    args = p.parse_args()

    if args.term in ("month", "year") and args.count <= 0:
        raise SystemExit("--count 必须为正整数")

    if not args.machine_id:
        raise SystemExit("至少需要一个 --machine-id")

    issued = now_utc()
    license_id = args.license_id.strip() or make_license_id(issued)

    term = Term(kind=args.term, count=int(args.count))
    validity = build_validity(term, issued)

    obj = {
        "license_version": LICENSE_VERSION,
        "product": PRODUCT_ID,
        "license_id": license_id,
        "issued_at": to_rfc3339_z(issued),
        "validity": validity,
        "customer": {"name": args.customer_name, "contact": args.customer_contact},
        "binding": {"type": "machine", "machine_ids": args.machine_id},
        "migration": {"mode": "manual", "note": "需人工换机：请联系授权方签发新 license"},
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"已生成未签名 license：{args.out}")
    print("下一步签名示例：")
    print(
        'python scripts/license_sign.py --in "{in_path}" --out license.json --key-id K1 --private-key-b64 "<PRIVATE_KEY_B64>"'.format(
            in_path=args.out
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

