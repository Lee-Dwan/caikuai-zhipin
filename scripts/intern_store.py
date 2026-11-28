"""实习岗位数据仓库：字段补全、去重、新增/下架判定、快照输出。

与社招 store.py 分离，输出到 data/intern/，互不影响。
缺失的非必备字段一律「未披露」，绝不推测。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone

from normalize import clean_text, make_id, normalize_city, summarize

CST = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "intern")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
UNKNOWN = "未披露"
CLOSED_KEEP_DAYS = 120
MISS_THRESHOLD = 2


def now_iso():
    return datetime.now(CST).replace(microsecond=0).isoformat()


def _tid(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


# ---------------- 字段推断 ----------------

def infer_intern_type(title, req=""):
    t = (title + " " + req).lower()
    if any(k in t for k in ("税务",)):
        return "税务实习"
    if any(k in t for k in ("咨询", "顾问", "风险", "内控", "并购", "交易", "战略", "数字化")):
        return "咨询实习"
    if any(k in t for k in ("评估", "估值")):
        return "资产评估实习"
    if any(k in t for k in ("寒假", "暑假", "暑期", "寒暑", "冬令", "summer", "winter")):
        return "寒暑假实习"
    if any(k in t for k in ("年审", "年报", "忙季")):
        return "年报审计实习"
    if any(k in t for k in ("审计", "assurance", "鉴证", "函证")):
        return "日常审计实习"
    return "其他实习"


def extract_education(req):
    s = clean_text(req)
    if not s:
        return UNKNOWN
    edu = ""
    for k in ("博士", "硕士", "研究生", "本科", "大专", "专科"):
        if k in s:
            edu = k
            break
    if "学历不限" in s and not edu:
        edu = "学历不限"
    majors = []
    for k in ("会计", "审计", "财务", "税务", "金融", "经济", "财政", "财会"):
        if k in s:
            majors.append(k)
    if "专业不限" in s:
        majors = ["专业不限"]
    parts = []
    if edu:
        parts.append(edu)
    if majors:
        parts.append("专业：" + "、".join(dict.fromkeys(majors)))
    return "；".join(parts) if parts else UNKNOWN


def extract_duration(req):
    m = re.search(r"(?:连续|可)?\s*实习\s*(?:时间\s*)?([一二两三四五六七八九十\d]+)\s*个?\s*月", req)
    if m:
        return f"约{m.group(1)}个月"
    m = re.search(r"(\d+)\s*个?\s*月", req)
    if m:
        return f"约{m.group(1)}个月"
    return UNKNOWN


def extract_weekly(req):
    m = re.search(r"每周\s*([1-7])\s*天", req)
    if m:
        return f"每周{m.group(1)}天"
    m = re.search(r"([1-7])\s*天\s*/\s*周", req)
    if m:
        return f"每周{m.group(1)}天"
    return UNKNOWN


def extract_salary(req):
    m = re.search(r"(\d+(?:[-~—]\d+)?)\s*元\s*/\s*(天|日|月)", req)
    if m:
        return f"{m.group(1)}元/{m.group(2)}"
    return UNKNOWN


def extract_housing(req):
    if any(k in req for k in ("提供住宿", "提供宿舍", "包住宿", "包住", "安排住宿", "免费住宿")):
        return "提供住宿"
    if any(k in req for k in ("不提供住宿", "不提供宿舍", "住宿自理", "食宿自理")):
        return "不提供住宿"
    if "住宿" in req or "宿舍" in req:
        return "以官方说明为准"
    return UNKNOWN


def extract_start(req):
    m = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月", req)
    if m:
        return f"{m.group(1)}年{m.group(2)}月"
    if any(k in req for k in ("尽快到岗", "立即到岗", "随时到岗")):
        return "尽快到岗"
    return UNKNOWN


def extract_email(text):
    m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text or "")
    return m.group(0) if m else ""


def extract_deadline(req):
    m = re.search(r"截止[^\d]{0,6}(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})?", req)
    if m:
        d = f"{m.group(1)}-{m.group(2).zfill(2)}"
        if m.group(3):
            d += f"-{m.group(3).zfill(2)}"
        return d
    m = re.search(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})[日号]?", req)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return UNKNOWN


def normalize_intern_job(raw):
    city, prov = normalize_city(raw.city or raw.province)
    req = clean_text(raw.requirements, 3000)
    resp = clean_text(raw.responsibilities, 2400)
    title = clean_text(raw.title, 120)
    combined = f"{title} {resp} {req}"
    email = raw.apply_email or extract_email(req)
    deadline = raw.deadline if raw.deadline and raw.deadline != UNKNOWN else extract_deadline(req)
    return {
        "id": make_id(raw.firm_id, title, city, raw.url),
        "title": title,
        "firm": raw.firm_name,
        "firm_id": raw.firm_id,
        "city": city,
        "province": prov,
        "intern_type": infer_intern_type(title, req),
        "education": raw.education or extract_education(req),
        "intern_start": raw.intern_start or extract_start(req),
        "duration": raw.duration or extract_duration(req),
        "weekly_attendance": raw.weekly_attendance or extract_weekly(req),
        "salary": raw.salary or extract_salary(req),
        "housing": raw.housing or extract_housing(req),
        "published_at": (raw.published_at or "")[:10],
        "deadline": deadline,
        "url": raw.url,
        "apply_email": email,
        "summary": summarize(resp or req),
        "responsibilities": resp,
        "requirements": req,
        "headcount": raw.headcount or UNKNOWN,
        "branch": clean_text(raw.branch, 40),
        "employment_type": "实习",
        "source_name": raw.source_name or raw.homepage,
        "homepage": raw.homepage,
    }


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(path + ".tmp", path)


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"version": 1, "jobs": {}, "firm_last_ok": {}}


def merge(state, results, meta_map):
    ts = now_iso()
    today = ts[:10]
    stats = {"new": 0, "updated": 0, "unchanged": 0, "closed": 0, "reopened": 0}
    jobs = state.setdefault("jobs", {})

    for firm_id, firm_name, ok, raws, err in results:
        if not ok:
            continue
        meta = meta_map.get(firm_id, {})
        seen = set()
        for raw in raws:
            job = normalize_intern_job(raw)
            if not job["title"] or not job["url"]:
                continue
            seen.add(job["id"])
            old = jobs.get(job["id"])
            if old is None:
                job.update({"first_seen": today, "last_seen": today, "status": "active",
                            "miss_count": 0, "created_at": ts, "updated_at": ts,
                            "verified_at": ts})
                jobs[job["id"]] = job
                stats["new"] += 1
            else:
                changed = False
                for k, v in job.items():
                    if v in ("", [], None, UNKNOWN) and old.get(k) in ("", [], None, UNKNOWN):
                        continue
                    if v in ("", [], None):
                        continue
                    if old.get(k) != v:
                        old[k] = v
                        changed = True
                old["last_seen"] = today
                old["miss_count"] = 0
                old["verified_at"] = ts
                if old.get("status") == "closed":
                    old["status"] = "active"
                    stats["reopened"] += 1
                if changed:
                    old["updated_at"] = ts
                    stats["updated"] += 1
                else:
                    stats["unchanged"] += 1

        for jid, job in jobs.items():
            if job.get("firm_id") != firm_id or job.get("status") != "active" or jid in seen:
                continue
            job["miss_count"] = job.get("miss_count", 0) + 1
            if job["miss_count"] >= MISS_THRESHOLD:
                job["status"] = "closed"
                job["closed_at"] = today
                stats["closed"] += 1

        state.setdefault("firm_last_ok", {})[firm_id] = ts

    cutoff = (datetime.now(CST) - timedelta(days=CLOSED_KEEP_DAYS)).strftime("%Y-%m-%d")
    for jid in list(jobs):
        j = jobs[jid]
        if j.get("status") == "closed" and j.get("closed_at", "9999") < cutoff:
            del jobs[jid]

    state.setdefault("baseline_at", today)
    state.setdefault("baseline_zero_date", today)
    state["updated_at"] = ts
    state["last_run"] = {"at": ts, "stats": stats}
    return stats


def build_public(state, firm_status, meta_map):
    ts = now_iso()
    rows = [j for j in state.get("jobs", {}).values() if j.get("status") == "active"]
    rows.sort(key=lambda j: (j.get("published_at") or j.get("first_seen") or "", j.get("firm", "")), reverse=True)
    today = ts[:10]
    firm_ids = {j["firm_id"] for j in rows}
    covered = [meta_map[fid]["name"] for fid in firm_ids if fid in meta_map]
    failed = [{"firm_id": fid, "name": meta_map[fid]["name"], "error": f.get("error", "")}
              for fid, f in firm_status.items()
              if f.get("status") == "failed" and fid in meta_map]

    public_rows = []
    for j in rows:
        item = {k: j.get(k) for k in (
            "id", "title", "firm", "firm_id", "city", "province", "intern_type", "education",
            "intern_start", "duration", "weekly_attendance", "salary", "housing",
            "published_at", "deadline", "url", "apply_email", "summary",
            "responsibilities", "requirements", "headcount", "branch", "employment_type",
            "source_name")}
        item["first_seen"] = j.get("first_seen")
        item["last_seen"] = j.get("last_seen")
        item["verified_at"] = j.get("verified_at")
        item["status"] = "active"
        public_rows.append(item)

    today_new = 0 if today == state.get("baseline_zero_date", today) else sum(
        1 for j in rows if (j.get("first_seen") or "")[:10] == today)
    meta = {
        "generated_at": ts,
        "active_jobs": len(rows),
        "firm_count": len(covered),
        "today_new": today_new,
        "covered_firms": covered,
        "failed_firms": failed,
        "firms_status": [f for f in firm_status.values()],
        "source_policy": "仅收录会计师事务所/税务师事务所/资产评估机构官方公开招聘渠道发布的实习岗位；来源经核验，不收录收费实习与付费内推",
    }
    return {"meta": meta, "jobs": public_rows}


def write_fallback(public):
    path = os.path.join(ROOT, "assets", "js", "data-fallback-intern.js")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("window.__INTERN_JOBS_DATA = " + json.dumps(public, ensure_ascii=False, separators=(",", ":")) + ";\n")
