"""实习岗位采集入口：抓取 → 补全字段 → 去重/新增/下架判定 → 输出。

用法：
    python3 scripts/collect_intern.py               # 全量
    python3 scripts/collect_intern.py --firms bdo   # 指定事务所
    python3 scripts/collect_intern.py --no-merge    # 只抓不落库（调试）
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import intern_collectors  # noqa: E402
from intern_collectors import all_intern_collectors  # noqa: E402
import intern_store as store  # noqa: E402


def firm_meta(collectors) -> dict:
    return {c.firm_id: {"name": c.firm_name, "source_name": c.source_name,
                        "homepage": c.homepage, "enabled": c.enabled} for c in collectors}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--firms", default="", help="逗号分隔的 firm_id，留空为全部")
    ap.add_argument("--no-merge", action="store_true")
    args = ap.parse_args()

    targets = all_intern_collectors()
    if args.firms:
        wanted = {s.strip() for s in args.firms.split(",") if s.strip()}
        targets = [c for c in targets if c.firm_id in wanted]
    meta_map = firm_meta(all_intern_collectors())

    print(f"开始采集实习岗位，共 {len(targets)} 个数据源：{', '.join(c.firm_name for c in targets)}")
    results = []
    for c in targets:
        ok, jobs, note = c.run()
        results.append((c.firm_id, c.firm_name, ok, jobs, note))
        flag = "OK  " if ok else "FAIL"
        print(f"  [{flag}] {c.firm_name:<8} {len(jobs):>4} 条  {note}")

    state = store.load_state()
    prev_status = {f["firm_id"]: f for f in (state.get("firms_status") or [])}
    stats = store.merge(state, results, meta_map) if not args.no_merge else {"new": 0, "updated": 0, "unchanged": 0, "closed": 0, "reopened": 0}

    firm_status = {}
    for c in all_intern_collectors():
        if c.firm_id in prev_status:
            firm_status[c.firm_id] = prev_status[c.firm_id]
    for firm_id, firm_name, ok, jobs, note in results:
        firm_status[firm_id] = {
            "firm_id": firm_id, "name": firm_name,
            "status": "ok" if ok else "failed",
            "count": len(jobs), "error": note, "note": note,
            "at": store.now_iso(),
        }
    state["firms_status"] = sorted(firm_status.values(), key=lambda f: f["name"])

    if args.no_merge:
        print("调试模式：未写入数据")
        return 0

    attempted = len(results)
    succeeded = sum(1 for r in results if r[2])
    report = {"at": store.now_iso(), "attempted": attempted, "succeeded": succeeded,
              "success_rate": round(succeeded / attempted * 100, 1) if attempted else 0,
              "stats": stats,
              "results": [{"firm_id": r[0], "firm_name": r[1], "ok": r[2],
                           "count": len(r[3]), "error": r[4]} for r in results]}
    state["last_report"] = report

    public = store.build_public(state, firm_status, meta_map)
    public["meta"]["collection"] = {"attempted": attempted, "succeeded": succeeded,
                                    "success_rate": report["success_rate"], "at": report["at"]}

    store.save_json(os.path.join(store.DATA_DIR, "jobs.json"), public)
    store.save_json(os.path.join(store.DATA_DIR, "meta.json"), public["meta"])
    store.save_json(os.path.join(store.DATA_DIR, "firms.json"),
                    {"generated_at": public["meta"]["generated_at"],
                     "firms": [{"firm_id": k, **v} for k, v in sorted(meta_map.items())]})
    store.save_json(os.path.join(store.DATA_DIR, "collect-report.json"), report)
    store.save_json(store.STATE_PATH, state)
    store.write_fallback(public)

    print(f"\n实习采集完成：{succeeded}/{attempted} 成功（{report['success_rate']}%），"
          f"在招实习 {public['meta']['active_jobs']} 条，覆盖 {public['meta']['firm_count']} 家；"
          f"新增 {stats['new']}，更新 {stats['updated']}，下架 {stats['closed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
