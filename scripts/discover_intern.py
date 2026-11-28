"""实习招聘来源发现：每周探测候选渠道，输出到 data/intern/。

只做可达性探测与记录，不自动抓取；新来源需人工核验官方公开招聘渠道后再新增采集器。
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "intern")
SOURCES = os.path.join(DATA, "discovery-sources.json")
REPORT = os.path.join(DATA, "discovery-report.json")
NEW = os.path.join(DATA, "discovery-new.json")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

CANDIDATES = [
    {"id": "ncss", "name": "国家大学生就业服务平台", "category": "官方就业平台",
     "url": "https://www.ncss.cn/", "note": "实习岗位公开搜索接口存在反爬校验，需人工核验"},
    {"id": "cicpa", "name": "中国注册会计师协会", "category": "行业协会",
     "url": "https://www.cicpa.org.cn/", "note": "注协官网/各地注协实习信息，需逐站核验"},
    {"id": "cctaa", "name": "中国注册税务师协会", "category": "行业协会",
     "url": "https://www.cctaa.cn/", "note": "税务师事务所实习信息，需逐站核验"},
    {"id": "cas", "name": "中国资产评估协会", "category": "行业协会",
     "url": "https://www.cas.org.cn/", "note": "资产评估机构实习信息，需逐站核验"},
    {"id": "shanghai-cicpa", "name": "上海市注册会计师协会", "category": "地方注协",
     "url": "https://www.shcpa.org.cn/", "note": "地方注协实习/招聘信息，需逐站核验"},
    {"id": "jiangsu-cicpa", "name": "江苏省注册会计师协会", "category": "地方注协",
     "url": "http://www.jscpa.org.cn/", "note": "地方注协实习/招聘信息，需逐站核验"},
    {"id": "guangdong-cicpa", "name": "广东省注册会计师协会", "category": "地方注协",
     "url": "http://www.gdicpa.org.cn/", "note": "地方注协实习/招聘信息，需逐站核验"},
]


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.localtime(time.time() + 8 * 3600))


def probe(url):
    for i in range(2):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=15, verify=False)
            if r.status_code == 200:
                return "reachable", r.status_code
            if r.status_code in (403, 429):
                return "blocked", r.status_code
            return f"http_{r.status_code}", r.status_code
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}"
            time.sleep(1)
    return "error", last


def main():
    sources = []
    if os.path.exists(SOURCES):
        try:
            sources = json.load(open(SOURCES, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            sources = []
    by_id = {s["id"]: s for s in sources}
    for c in CANDIDATES:
        item = by_id.get(c["id"], {**c, "status": "pending", "last_check": "", "last_note": ""})
        item.update({k: c[k] for k in ("id", "name", "category", "url", "note")})
        status, detail = probe(c["url"])
        item["status"] = status
        item["last_check"] = now()
        item["last_note"] = detail
        by_id[c["id"]] = item
    sources = [by_id[c["id"]] for c in CANDIDATES]

    os.makedirs(DATA, exist_ok=True)
    with open(SOURCES, "w", encoding="utf-8") as f:
        json.dump(sources, f, ensure_ascii=False, indent=1)

    reachable = [s for s in sources if s["status"] in ("reachable", "reachable_with_social")]
    new_candidates = [s for s in reachable if s.get("status") == "reachable" and "人工核验" in s.get("note", "")]
    report = {"at": now(), "checked": len(sources),
              "reachable": len(reachable),
              "note": "仅探测可达性，未自动采集；实习新来源须人工核验官方公开招聘渠道后接入。"}
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    with open(NEW, "w", encoding="utf-8") as f:
        json.dump(new_candidates, f, ensure_ascii=False, indent=1)

    print(f"实习来源发现：探测 {len(sources)} 个，可达 {len(reachable)} 个，待核验候选 {len(new_candidates)} 个")


if __name__ == "__main__":
    main()
