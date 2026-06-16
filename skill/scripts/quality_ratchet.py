#!/usr/bin/env python3
"""质量棘轮 - 防止质量退化"""
import json
from pathlib import Path

BASELINE_FILE = Path(".baseline/deliverhq-score.json")

def check_regression(current_score):
    """检查是否退化"""
    if not BASELINE_FILE.exists():
        print("⚠️  无基线，保存当前分数")
        BASELINE_FILE.parent.mkdir(exist_ok=True)
        BASELINE_FILE.write_text(json.dumps(current_score, indent=2))
        return True
    
    baseline = json.loads(BASELINE_FILE.read_text())
    if current_score['total'] < baseline['total']:
        print(f"❌ 分数退化: {baseline['total']} → {current_score['total']}")
        return False
    print(f"✅ 分数保持: {current_score['total']}")
    return True

if __name__ == "__main__":
    # 测试
    score = {"total": 69, "dimensions": {}}
    check_regression(score)
