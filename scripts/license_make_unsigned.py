"""
生成未签名的 license_unsigned.json（离线授权）。

示例：
  # 永久（默认输出 scripts/<客户名>_<联系方式>_license_unsigned.json，可用 --out 覆盖）
  python scripts/license_make_unsigned.py \
    --term perpetual \
    --customer-name "客户A" \
    --customer-contact "a@example.com" \
    --machine-id "MID-XXXX"

  # 年付 1 年，显式指定输出路径
  python scripts/license_make_unsigned.py \
    --term year --count 1 \
    --customer-name "客户A" \
    --customer-contact "a@example.com" \
    --machine-id "MID-XXXX" \
    --out scripts/my_custom_unsigned.json

  # 月付 3 个月 + 绑定两台（省略 --out 时默认写入
  # scripts/<customer-name>_<customer-contact>_license_unsigned.json）
  python scripts/license_make_unsigned.py \
    --term month --count 3 \
    --customer-name "客户A" \
    --customer-contact "a@example.com" \
    --machine-id "MID-1" --machine-id "MID-2"
"""

from __future__ import annotations

import argparse
import json
import os

from license_common import build_unsigned_license_object, make_license_id, now_utc, sanitize_for_filename


def default_unsigned_out_path(customer_name: str, customer_contact: str) -> str:
    sn = sanitize_for_filename(customer_name)
    sc = sanitize_for_filename(customer_contact)
    if sn and sc:
        base = f"{sn}_{sc}_license_unsigned.json"
    elif sn:
        base = f"{sn}_license_unsigned.json"
    elif sc:
        base = f"{sc}_license_unsigned.json"
    else:
        base = "license_unsigned.json"
    return os.path.join("scripts", base)


def main() -> int:
    p = argparse.ArgumentParser(description="Generate unsigned license JSON")
    p.add_argument("--term", choices=["perpetual", "month", "year"], required=True, help="授权类型：永久/月付/年付")
    p.add_argument("--count", type=int, default=1, help="月付/年付的数量（默认 1）")
    p.add_argument("--customer-name", required=True, help="客户名称")
    p.add_argument("--customer-contact", default="", help="客户联系方式（邮箱/手机号等）")
    p.add_argument("--machine-id", action="append", default=[], help="绑定机器码 MID-...（可多次传入）")
    p.add_argument("--license-id", default="", help="自定义 license_id（不传则自动生成）")
    p.add_argument(
        "--out",
        default=None,
        help="输出路径；省略则使用 scripts/<customer-name>_<customer-contact>_license_unsigned.json",
    )
    args = p.parse_args()
    out_path = args.out if args.out is not None else default_unsigned_out_path(args.customer_name, args.customer_contact)

    if args.term in ("month", "year") and args.count <= 0:
        raise SystemExit("--count 必须为正整数")

    if not args.machine_id:
        raise SystemExit("至少需要一个 --machine-id")

    issued = now_utc()
    license_id = args.license_id.strip() or make_license_id(issued)

    obj = build_unsigned_license_object(
        term_kind=args.term,
        term_count=int(args.count),
        customer_name=args.customer_name,
        customer_contact=args.customer_contact,
        machine_ids=args.machine_id,
        license_id=license_id,
        issued=issued,
    )

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"已生成未签名 license：{out_path}")
    print("下一步：文件签名或一步签发（推荐）：")
    print(f'  python scripts/license_sign.py --in "{out_path}" --out license.json --key-id K1 --private-key-b64 "<PRIVATE_KEY_B64>"')
    print(
        "  python scripts/license_sign.py --issue --term "
        f"{args.term} --customer-name ... --machine-id ... --key-id K1 --private-key-b64 \"<PRIVATE_KEY_B64>\""
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
