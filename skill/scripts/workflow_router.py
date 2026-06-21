#!/usr/bin/env python3
"""
Lightweight DeliverHQ workflow router.

规则优先，不接 LLM。输入用户请求，输出可解释 JSON。
定位：低噪主动提醒，不做复杂多 Agent 编排。
"""

import argparse
import json
import sys

from routing_rules import route_request


def main():
    parser = argparse.ArgumentParser(description="Route a user request to a low-noise DeliverHQ workflow decision")
    parser.add_argument("prompt", nargs="*", help="user request text")
    args = parser.parse_args()

    text = " ".join(args.prompt).strip()
    if not text:
        text = sys.stdin.read().strip()
    if not text:
        print(json.dumps({"error": "empty prompt"}, ensure_ascii=False, indent=2))
        sys.exit(1)

    print(json.dumps(route_request(text), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
