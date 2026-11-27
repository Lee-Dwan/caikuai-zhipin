"""采集入口：抓取 → 清洗 → 去重/新增/下架判定 → 输出 JSON 与报告。

用法：
    python3 scripts/collect.py                # 全量
    python3 scripts/collect.py --firms tianjian,ey   # 指定事务所
    python3 scripts/collect.py --no-merge     # 只抓不落库（调试）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import collectors  # noqa: E402
from collectors.base import all_collectors  # noqa: E402
import store  # noqa: E402

# 已核实「无公开社招岗位列表」的机构，如实记录原因，不编造岗位
NO_PUBLIC = {
    "pwc": {"name": "普华永道", "reason": "官网(Workday)存在频率限制，CX 接口持续返回 429，无法稳定自动采集；仅保留官网入口",
            "homepage": "https://www.pwccn.com/zh/careers/experienced-jobs.html"},
    "deloitte": {"name": "德勤", "reason": "官方招聘门户为 SuccessFactors/wecruit，需登录交互，未开放公开岗位列表接口",
                 "homepage": "https://ehjobs.deloitte.com.cn/SU649e304a6a9f0ef690533e9a/pb/index.html"},
    "kpmg": {"name": "毕马威", "reason": "官网招聘页无岗位列表与公开接口（job-search 页面 404）",
             "homepage": "https://kpmg.com/cn/zh/careers/experienced-hires.html"},
    "tianheng": {"name": "天衡", "reason": "官网 join-us 栏目仅有校园招聘信息，暂无公开社招岗位",
                 "homepage": "https://www.jscpa.com.cn/join-us/"},
    "suyajc": {"name": "苏亚金诚", "reason": "官网仅有招聘简介与邮箱投递方式，无结构化岗位列表",
               "homepage": "https://syjc.com/cpycsp.html"},
}


def firm_meta(collectors_list) -> dict:
    meta = {}
    for c in collectors_list:
        meta[c.firm_id] = {"name": c.firm_name, "source_name": c.source_name,
                           "homepage": c.homepage, "enabled": c.enabled}
    for fid, info in NO_PUBLIC.items():
        meta.setdefault(fid, {"name": info["name"], "source_name": "官方招聘页面（无公开岗位列表）",
                              "homepage": info["homepage"], "enabled": False, "reason": info["reason"]})
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--firms", default="", help="逗号分隔的 firm_id，留空为全部")
    ap.add_argument("--no-merge", action="store_true")
    args = ap.parse_args()

    collectors.load_all()
    targets = all_collectors()
    if args.firms:
        wanted = {s.strip() for s in args.firms.split(",") if s.strip()}
        targets = [c for c in targets if c.firm_id in wanted]
    meta_map = firm_meta(all_collectors() + [])
    for fid, info in NO_PUBLIC.items():
        meta_map.setdefault(fid, {"name": info["name"], "source_name": "官方招聘页面（无公开岗位列表）",
                                  "homepage": info["homepage"], "enabled": False, "reason": info["reason"]})

    print(f"开始采集，共 {len(targets)} 个数据源：{', '.join(c.firm_name for c in targets)}")
    results = []
    for c in targets:
        t0 = time.time()
        res = c.run()
        results.append(res)
        flag = "OK  " if res.ok else "FAIL"
        print(f"  [{flag}] {res.firm_name:<6} {len(res.jobs):>4} 条  {time.time() - t0:.1f}s  {res.error or res.note}")

    state = store.load_state()
    prev_status = {f["firm_id"]: f for f in (state.get("firms_status") or [])}
    stats = store.merge(state, results, meta_map) if not args.no_merge else {"new": 0, "updated": 0, "unchanged": 0, "closed": 0, "reopened": 0}

    # 事务所状态：本轮未参与的沿用上一轮，避免局部采集把其它所显示为异常
    firm_status = []
    for c in all_collectors():
        if c.firm_id in prev_status:
            firm_status.append(prev_status[c.firm_id])
    for res in results:
        firm_status = [f for f in firm_status if f["firm_id"] != res.firm_id]
        firm_status.append({
            "firm_id": res.firm_id, "name": res.firm_name,
            "status": "ok" if res.ok else "failed",
            "count": len(res.jobs), "error": res.error, "note": res.note,
            "at": store.now_iso(), "duration": round(res.duration, 1),
        })
    for fid, info in NO_PUBLIC.items():
        firm_status.append({"firm_id": fid, "name": info["name"], "status": "not_collected",
                            "count": 0, "error": "", "note": info["reason"], "at": store.now_iso()})
    firm_status = sorted(firm_status, key=lambda f: f["name"])
    state["firms_status"] = firm_status

    if args.no_merge:
        print("调试模式：未写入数据")
        return 0

    attempted = len(results)
    succeeded = sum(1 for r in results if r.ok)
    report = {"at": store.now_iso(), "attempted": attempted, "succeeded": succeeded,
              "success_rate": round(succeeded / attempted * 100, 1) if attempted else 0,
              "stats": stats, "results": [r.to_report() for r in results]}
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

    write_markdown(report, public)

    print(f"\n采集完成：{succeeded}/{attempted} 成功（{report['success_rate']}%），"
          f"在招 {public['meta']['active_jobs']} 条，覆盖 {public['meta']['firm_count']} 家；"
          f"新增 {stats['new']}，更新 {stats['updated']}，下架 {stats['closed']}")
    return 0


def write_markdown(report, public):
    path = os.path.join(store.ROOT, "reports", "latest.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    meta = public["meta"]
    lines = [
        "# 采集报告", "",
        f"- 采集时间：{report['at']}（北京时间）",
        f"- 成功率：{report['succeeded']}/{report['attempted']}（{report['success_rate']}%）",
        f"- 在招岗位：{meta['active_jobs']} 条；覆盖事务所：{meta['firm_count']} 家；今日新增：{meta['today_new']}",
        "", "## 各数据源", "", "| 事务所 | 状态 | 条数 | 耗时(s) | 说明 |", "| --- | --- | --- | --- | --- |",
    ]
    for r in report["results"]:
        lines.append(f"| {r['firm_name']} | {'成功' if r['ok'] else '失败'} | {r['count']} | {r['duration']} | {r['error'] or r['note'] or '-'} |")
    lines += ["", "## 未纳入自动采集", ""]
    for fid, f in [(f["firm_id"], f) for f in meta.get("firms_status", []) if f["status"] == "not_collected"]:
        lines.append(f"- **{f['name']}**：{f['note']}")
    lines += ["", "## 数据口径", "",
              "- 仅收录社会招聘，校招/实习岗位在采集阶段即被排除；",
              "- 岗位连续 2 次采集成功且官网未再出现才判定下架；采集失败时保留历史数据并标记异常；",
              "- 投递链接均指向事务所官方页面。"]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
