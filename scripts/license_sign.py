"""
离线签发工具（Ed25519）：

用法：
  python scripts/license_sign.py \
    --in license_unsigned.json \
    --out license.json \
    --key-id K1 \
    --private-key-b64 <ED25519_PRIVATE_KEY_B64>
"""

import argparse
import base64
import json
from typing import Any, Dict

from cryptography.hazmat.primitives.asymmetric import ed25519


def canonical_dumps(obj: Dict[str, Any]) -> bytes:
    # 按字典序排序 + 最小化空白，确保签名稳定
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Sign a license.json with Ed25519 (offline)")
    p.add_argument("--in", dest="in_path", required=True, help="未签名的 license JSON（不含 signature 字段）")
    p.add_argument("--out", dest="out_path", required=True, help="输出签名后的 license.json")
    p.add_argument("--key-id", required=True, help="公钥标识，例如 K1")
    p.add_argument("--private-key-b64", required=True, help="Ed25519 私钥 raw bytes 的 base64")
    args = p.parse_args()

    with open(args.in_path, "r", encoding="utf-8") as f:
        license_obj = json.load(f)

    if "signature" in license_obj:
        raise SystemExit("输入 JSON 不应包含 signature 字段，请删除后再签名。")

    priv_raw = base64.b64decode(args.private_key_b64)
    priv = ed25519.Ed25519PrivateKey.from_private_bytes(priv_raw)

    payload = canonical_dumps(license_obj)
    sig = priv.sign(payload)

    license_obj["signature"] = {
        "alg": "ed25519",
        "key_id": args.key_id,
        "value": base64.b64encode(sig).decode("ascii"),
    }

    with open(args.out_path, "w", encoding="utf-8") as f:
        json.dump(license_obj, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"已签名输出：{args.out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

