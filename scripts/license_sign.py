"""
离线签发工具（Ed25519）：

1) 从文件签名（需先有未签名 JSON）：
  python scripts/license_sign.py \
    --in license_unsigned.json \
    --out license.json \
    --key-id K1 \
    --private-key-b64 <ED25519_PRIVATE_KEY_B64>

2) 一步直接签发（无中间未签名文件，留底目录为「客户名@联系方式」）：
  python scripts/license_sign.py --issue \
    --term perpetual \
    --customer-name "客户A" \
    --customer-contact "a@example.com" \
    --machine-id "MID-XXXX" \
    --key-id K1 \
    --private-key-b64 <ED25519_PRIVATE_KEY_B64>
  # 生成：./<客户名@联系方式>/license.json（可用 --output-root 指定根目录）
"""

import argparse
import base64
import json
import os
from typing import Any, Dict

from cryptography.hazmat.primitives.asymmetric import ed25519

from license_common import (
    build_unsigned_license_object,
    canonical_license_bytes,
    customer_archive_dir_name,
    make_license_id,
    now_utc,
)


def sign_license_inplace(license_obj: Dict[str, Any], key_id: str, private_key_b64: str) -> None:
    if "signature" in license_obj:
        raise SystemExit("license 对象不应包含 signature 字段。")
    priv_raw = base64.b64decode(private_key_b64)
    priv = ed25519.Ed25519PrivateKey.from_private_bytes(priv_raw)
    payload = canonical_license_bytes(license_obj)
    sig = priv.sign(payload)
    license_obj["signature"] = {
        "alg": "ed25519",
        "key_id": key_id,
        "value": base64.b64encode(sig).decode("ascii"),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Sign license.json with Ed25519 (offline)")
    p.add_argument("--key-id", required=True, help="公钥标识，例如 K1")
    p.add_argument("--private-key-b64", required=True, help="Ed25519 私钥 raw bytes 的 base64")

    p.add_argument(
        "--issue",
        action="store_true",
        help="直接根据客户/机器/期限生成并签名，输出到「客户名@联系方式」目录下的 license.json",
    )
    p.add_argument("--term", choices=["perpetual", "month", "year"], help="--issue 时必填：永久/月付/年付")
    p.add_argument("--count", type=int, default=1, help="--issue 时：月付/年付数量（默认 1）")
    p.add_argument("--customer-name", default="", help="--issue 时必填：客户名称")
    p.add_argument("--customer-contact", default="", help="--issue 时：客户联系方式")
    p.add_argument("--machine-id", action="append", default=[], help="--issue 时：机器码（可多次）")
    p.add_argument("--license-id", default="", help="--issue 时：自定义 license_id（可选）")
    p.add_argument(
        "--output-root",
        default=".",
        help="--issue 时：留底根目录（默认当前目录，其下创建「客户名@联系方式」文件夹）",
    )

    p.add_argument("--in", dest="in_path", default=None, help="未签名 JSON 路径（与 --issue 二选一）")
    p.add_argument("--out", dest="out_path", default=None, help="签名后输出路径（文件模式必填）")

    args = p.parse_args()

    if args.issue:
        if args.in_path or args.out_path:
            raise SystemExit("使用 --issue 时不要指定 --in / --out。")
        if not args.term:
            raise SystemExit("--issue 需要指定 --term")
        if not args.customer_name.strip():
            raise SystemExit("--issue 需要 --customer-name")
        if not args.machine_id:
            raise SystemExit("--issue 需要至少一个 --machine-id")
        if args.term in ("month", "year") and args.count <= 0:
            raise SystemExit("--count 必须为正整数")

        issued = now_utc()
        lid = args.license_id.strip() or make_license_id(issued)
        license_obj = build_unsigned_license_object(
            term_kind=args.term,
            term_count=int(args.count),
            customer_name=args.customer_name,
            customer_contact=args.customer_contact,
            machine_ids=args.machine_id,
            license_id=lid,
            issued=issued,
        )
        sign_license_inplace(license_obj, args.key_id, args.private_key_b64)

        sub = customer_archive_dir_name(args.customer_name, args.customer_contact)
        out_dir = os.path.abspath(os.path.join(args.output_root, sub))
        os.makedirs(out_dir, exist_ok=True)
        final_path = os.path.join(out_dir, "license.json")
        with open(final_path, "w", encoding="utf-8") as f:
            json.dump(license_obj, f, ensure_ascii=False, indent=2)
            f.write("\n")

        print(f"已签发（留底）：{final_path}")
        print("可将该 license.json 发给客户，置于程序目录或与 --license-path 配合使用。")
        return 0

    # 文件模式
    if not args.in_path or not args.out_path:
        raise SystemExit("请使用「文件模式」：--in <未签名.json> --out <签名后.json>；或「一步签发」：--issue ...")
    with open(args.in_path, "r", encoding="utf-8") as f:
        license_obj = json.load(f)

    if "signature" in license_obj:
        raise SystemExit("输入 JSON 不应包含 signature 字段，请删除后再签名。")

    sign_license_inplace(license_obj, args.key_id, args.private_key_b64)

    with open(args.out_path, "w", encoding="utf-8") as f:
        json.dump(license_obj, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"已签名输出：{args.out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
