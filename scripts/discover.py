"""每周招聘来源发现：探测候选来源是否可访问、是否疑似含社招入口。

只做「发现与标记」，不自动抓取岗位、不自动上线新数据源：
- 探测结果写入 data/discovery-sources.json（累计状态）
- 结构化报告写入 data/discovery-report.json
- 可读报告写入 reports/discovery.md
- 待人工验证的新候选写入 data/discovery-new.json（供 Actions 创建 Issue）

用法：
    python3 scripts/discover.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
SRC_PATH = os.path.join(DATA_DIR, "discovery-sources.json")
REPORT_PATH = os.path.join(DATA_DIR, "discovery-report.json")
NEW_PATH = os.path.join(DATA_DIR, "discovery-new.json")
MD_PATH = os.path.join(ROOT, "reports", "discovery.md")

UA = ("Mozilla/5.0 (compatible; CaiKuaiZhipinBot/1.1; +https://github.com/Lee-Dwan/caikuai-zhipin) "
      "Python-Requests/2")
TIMEOUT = 15
MAX_BYTES = 300_000

SOCIAL_MARKERS = ["社会招聘", "社招", "社会招聘职位", "招聘职位", "岗位", "职位", "experienced",
                  "job", "career", "recruit", "招聘"]
CAMPUS_MARKERS = ["校园招聘", "校招", "应届", "应届生", "实习生", "campus", "graduate", "intern"]


def now():
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()


def fetch_text(url: str) -> tuple:
    """返回 (ok, text_or_error)。只读少量字节，遵守超时，不绕过登录。"""
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": UA}, stream=True)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        chunks = []
        size = 0
        for chunk in r.iter_content(chunk_size=8192):
            if not chunk:
                continue
            chunks.append(chunk)
            size += len(chunk)
            if size >= MAX_BYTES:
                break
        text = b"".join(chunks).decode("utf-8", errors="ignore")
        return True, text
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def classify(text: str) -> str:
    low = text.lower()
    has_social = any(m.lower() in low for m in SOCIAL_MARKERS)
    has_campus = any(m.lower() in low for m in CAMPUS_MARKERS)
    if has_social:
        return "reachable_with_social"
    if has_campus:
        return "only_campus"
    return "reachable"


def main() -> int:
    with open(SRC_PATH, encoding="utf-8") as f:
        data = json.load(f)

    results = []
    new_candidates = []
    for s in data["sources"]:
        url = s["url"]
        t0 = time.time()
        ok, text = fetch_text(url)
        dur = round(time.time() - t0, 1)
        if ok:
            kind = classify(text)
            # 已标记 verified 的来源不重复作为新候选；其余可访问且疑似社招的进入人工待验证清单
            if s.get("status") == "pending" and kind in ("reachable_with_social", "reachable"):
                new_candidates.append({"id": s["id"], "name": s["name"], "category": s["category"],
                                       "url": url, "signal": kind})
        else:
            kind = "blocked"
        result = {
            "id": s["id"], "name": s["name"], "category": s["category"], "url": url,
            "status": kind, "checked_at": now(), "duration": dur,
            "error": "" if ok else text,
        }
        results.append(result)
        s["status"] = kind
        s["last_check"] = result["checked_at"]
        s["last_note"] = result["error"] or kind
        print(f"[{kind:<22}] {s['name']:<14} {dur}s {result['error']}")

    data["updated_at"] = now()

    report = {
        "at": data["updated_at"],
        "total": len(results),
        "reachable_with_social": sum(1 for r in results if r["status"] == "reachable_with_social"),
        "reachable": sum(1 for r in results if r["status"] == "reachable"),
        "only_campus": sum(1 for r in results if r["status"] == "only_campus"),
        "blocked": sum(1 for r in results if r["status"] == "blocked"),
        "results": results,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(MD_PATH), exist_ok=True)
    write_json(SRC_PATH, data)
    write_json(REPORT_PATH, report)
    write_json(NEW_PATH, new_candidates)
    write_markdown(report)

    print(f"\n发现完成：可访问且疑似社招 {report['reachable_with_social']}，"
          f"可访问待确认 {report['reachable']}，仅校招 {report['only_campus']}，"
          f"不可访问 {report['blocked']}；待人工验证新候选 {len(new_candidates)} 个。")
    return 0


def write_json(path, obj):
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(path + ".tmp", path)


def write_markdown(report: dict):
    lines = [
        "# 每周招聘来源发现报告", "",
        f"- 探测时间：{report['at']}（北京时间）",
        f"- 汇总：可访问且疑似社招 {report['reachable_with_social']}；可访问待确认 {report['reachable']}；"
        f"仅校招 {report['only_campus']}；不可访问 {report['blocked']}",
        "", "| 来源 | 类别 | 状态 | 说明 |", "| --- | --- | --- | --- |",
    ]
    for r in report["results"]:
        status = {"reachable_with_social": "疑似有社招", "reachable": "可访问待确认",
                  "only_campus": "仅校招", "blocked": "不可访问"}.get(r["status"], r["status"])
        lines.append(f"| {r['name']} | {r['category']} | {status} | {r['error'] or '-'} |")
    lines += ["", "> 以上仅为基础探测信号，不直接上线。确认「疑似有社招」的来源后，需人工核对其官方公开招聘渠道",
              "> 与数据接口，再按 `scripts/collectors/` 现有模式新增采集器；验证通过前不会写入任何岗位数据。"]
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
