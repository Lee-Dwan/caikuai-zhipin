"""数据仓库：去重、新增识别、失效判定、快照输出。"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from normalize import clean_text, extract_certs, infer_category, make_id, normalize_city, summarize

CST = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
CLOSED_KEEP_DAYS = 120
MISS_THRESHOLD = 2   # 连续 2 次「采集成功但岗位消失」才判定下架


def now_iso():
    return datetime.now(CST).replace(microsecond=0).isoformat()


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"version": 1, "jobs": {}, "firm_last_ok": {}}


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(path + ".tmp", path)


def normalize_job(raw, firm_id, firm_name, source_name, homepage):
    raw_city = clean_text(raw.city, 30)
    city, prov = normalize_city(raw.city or raw.province)
    keep_branch = raw_city if (not city and raw_city and raw_city not in ("全国", "不限", "其他")) else ""
    if not prov:
        prov = normalize_city(raw.province)[1]
    req = clean_text(raw.requirements, 2400)
    resp = clean_text(raw.responsibilities, 2400)
    cat = (raw.category or "").strip()
    if cat not in ("审计", "税务", "咨询", "评估", "工程造价", "其他"):
        cat = infer_category(cat or raw.title, req)
    return {
        "id": make_id(firm_id, raw.title, city, raw.url),
        "title": clean_text(raw.title, 120),
        "firm": firm_name,
        "firm_id": firm_id,
        "city": city,
        "province": prov,
        "category": cat,
        "certs": extract_certs(f"{raw.title} {req}"),
        "published_at": (raw.published_at or "")[:10],
        "url": raw.url,
        "summary": raw.summary or summarize(resp or req),
        "responsibilities": resp,
        "requirements": req,
        "headcount": clean_text(raw.headcount, 12),
        "branch": clean_text(raw.branch, 40) or keep_branch,
        "employment_type": raw.employment_type or "社招",
        "source_name": source_name or homepage,
        "homepage": homepage,
    }


def merge(state, firm_results, firm_meta):
    ts = now_iso()
    today = ts[:10]
    stats = {"new": 0, "updated": 0, "unchanged": 0, "closed": 0, "reopened": 0}
    jobs = state.setdefault("jobs", {})

    for res in firm_results:
        if not res.ok:
            continue  # 采集失败：保留历史数据，不做下架判定
        meta = firm_meta.get(res.firm_id, {})
        seen = set()
        for raw in res.jobs:
            job = normalize_job(raw, res.firm_id, res.firm_name, meta.get("source_name", ""), meta.get("homepage", ""))
            if not job["title"] or not job["url"]:
                continue
            seen.add(job["id"])
            old = jobs.get(job["id"])
            if old is None:
                job.update({"first_seen": today, "last_seen": today, "status": "active",
                            "miss_count": 0, "created_at": ts, "updated_at": ts})
                jobs[job["id"]] = job
                stats["new"] += 1
            else:
                changed = False
                for k, v in job.items():
                    if v in ("", [], None):
                        continue
                    if old.get(k) != v:
                        old[k] = v
                        changed = True
                old["last_seen"] = today
                old["miss_count"] = 0
                if old.get("status") == "closed":
                    old["status"] = "active"
                    stats["reopened"] += 1
                if changed:
                    old["updated_at"] = ts
                    stats["updated"] += 1
                else:
                    stats["unchanged"] += 1

        for jid, job in jobs.items():
            if job.get("firm_id") != res.firm_id or job.get("status") != "active" or jid in seen:
                continue
            job["miss_count"] = job.get("miss_count", 0) + 1
            if job["miss_count"] >= MISS_THRESHOLD:
                job["status"] = "closed"
                job["closed_at"] = today
                stats["closed"] += 1

        state.setdefault("firm_last_ok", {})[res.firm_id] = ts

    cutoff = (datetime.now(CST) - timedelta(days=CLOSED_KEEP_DAYS)).strftime("%Y-%m-%d")
    for jid in list(jobs):
        j = jobs[jid]
        if j.get("status") == "closed" and j.get("closed_at", "9999") < cutoff:
            del jobs[jid]

    state.setdefault("baseline_at", ts[:10])
    state.setdefault("baseline_zero_date", ts[:10])
    state["updated_at"] = ts
    state["last_run"] = {"at": ts, "stats": stats}
    return stats


def active_jobs(state):
    rows = [j for j in state.get("jobs", {}).values() if j.get("status") == "active"]
    rows.sort(key=lambda j: (j.get("published_at") or j.get("first_seen") or "", j.get("firm", "")), reverse=True)
    return rows


def build_public(state, firm_status, firm_meta):
    ts = now_iso()
    rows = active_jobs(state)
    today = ts[:10]
    firm_ids = {j["firm_id"] for j in rows}
    status_by_id = {f["firm_id"]: f for f in firm_status}

    covered = [firm_meta[fid]["name"] for fid in firm_ids if fid in firm_meta]
    no_data = [firm_meta[fid]["name"] for fid, m in firm_meta.items()
               if m.get("enabled", True) and fid not in firm_ids
               and status_by_id.get(fid, {}).get("status") == "ok"]
    failed = [{"firm_id": fid, "name": firm_meta[fid]["name"], "error": f.get("error", "")}
              for fid, f in status_by_id.items() if f.get("status") == "failed"]

    public_rows = []
    for j in rows:
        item = {k: j.get(k) for k in (
            "id", "title", "firm", "firm_id", "city", "province", "category", "certs",
            "published_at", "url", "summary", "responsibilities", "requirements",
            "headcount", "branch", "employment_type", "source_name")}
        item["first_seen"] = j.get("first_seen")
        item["last_seen"] = j.get("last_seen")
        item["status"] = "active"
        public_rows.append(item)

    baseline = state.get("baseline_at") or today
    zero_day = state.get("baseline_zero_date", baseline)
    today_new = 0 if today == zero_day else sum(1 for j in rows if (j.get("first_seen") or "")[:10] == today)
    meta = {
        "generated_at": ts,
        "active_jobs": len(rows),
        "firm_count": len(covered),
        "today_new": today_new,
        "covered_firms": covered,
        "no_public_jobs": no_data,
        "failed_firms": failed,
        "firms_status": firm_status,
        "baseline_at": baseline,
        "source_policy": "仅采集事务所官网/官方招聘系统公开发布的社招岗位",
    }
    return {"meta": meta, "jobs": public_rows}


def write_fallback(public):
    path = os.path.join(ROOT, "assets", "js", "data-fallback.js")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("window.__JOBS_DATA = " + json.dumps(public, ensure_ascii=False, separators=(",", ":")) + ";\n")
