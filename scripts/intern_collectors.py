"""实习岗位采集器集合。

与「社会招聘」采集器完全独立：本文件只负责实习岗位，输出到 data/intern/。
真实数据来源：
- 北森 iTalent 门户「实习生招聘」类别（立信/天职国际/大信/中汇/致同/大华/中审众环）
- 天健官方招聘系统 jobPersonProperty=3（实习生招聘）
- 信永中和官方招聘系统 position_recruit=2（含实习）

原则：仅收录官方公开招聘渠道真实发布的实习岗位；缺字段一律「未披露」，绝不推测编造。
"""
from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from normalize import clean_text, normalize_city

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

UNKNOWN = "未披露"


@dataclass
class InternRawJob:
    title: str
    firm_id: str
    firm_name: str
    url: str
    source_name: str = ""
    homepage: str = ""
    city: str = ""
    province: str = ""
    published_at: str = ""
    deadline: str = ""
    responsibilities: str = ""
    requirements: str = ""
    education: str = ""
    intern_start: str = ""
    duration: str = ""
    weekly_attendance: str = ""
    salary: str = ""
    housing: str = ""
    headcount: str = ""
    branch: str = ""
    apply_email: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class InternCollector:
    firm_id: str = "unknown"
    firm_name: str = "未命名事务所"
    source_name: str = ""
    homepage: str = ""
    enabled: bool = True
    verify: bool = True

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        })

    def get(self, url: str, **kwargs):
        kwargs.setdefault("timeout", 25)
        last = None
        for i in range(3):
            try:
                r = self.session.get(url, verify=self.verify, **kwargs)
                if r.status_code in (200, 201, 202):
                    r.encoding = r.apparent_encoding or "utf-8"
                    return r
                last = RuntimeError(f"HTTP {r.status_code}")
                if r.status_code in (403, 404, 410):
                    break
            except Exception as e:  # noqa: BLE001
                last = e
            time.sleep(1.2 * (i + 1) + random.uniform(0, 0.6))
        raise RuntimeError(str(last) if last else f"request failed: {url}")

    def post_json(self, url: str, payload: dict, **kwargs):
        last = None
        for i in range(3):
            try:
                r = self.session.post(url, json=payload, timeout=25, verify=self.verify, **kwargs)
                if r.status_code < 400:
                    return r.json()
                last = RuntimeError(f"HTTP {r.status_code}")
                if r.status_code in (403, 404):
                    break
            except Exception as e:  # noqa: BLE001
                last = e
            time.sleep(1.2 * (i + 1) + random.uniform(0, 0.5))
        raise RuntimeError(str(last) if last else f"post failed: {url}")

    def fetch(self) -> list[InternRawJob]:
        raise NotImplementedError

    def run(self) -> tuple[bool, list[InternRawJob], str]:
        t0 = time.time()
        try:
            jobs = self.fetch()
            ok = bool(jobs)
            note = "" if jobs else "官网正常返回但本次未发现实习岗位"
            return ok, jobs, note if note else ""
        except Exception as e:  # noqa: BLE001
            return False, [], f"{type(e).__name__}: {e}"


REGISTRY: dict[str, InternCollector] = {}


def register(obj):
    c = obj() if isinstance(obj, type) else obj
    REGISTRY[c.firm_id] = c
    return obj


def all_intern_collectors():
    return sorted(REGISTRY.values(), key=lambda c: c.firm_id)


# ---------------- 北森 iTalent 通用实习采集器 ----------------

class ITalentInternCollector(InternCollector):
    portal_base = ""
    portal_id = ""
    list_page = "/social"
    list_path = "/api/Jobad/GetJobAdPageList"
    detail_path = "/jobs/detail"
    PAGE_SIZE = 200

    def fetch(self) -> list[InternRawJob]:
        rows: list[dict] = []
        index = 0
        while index <= 10:
            payload = {
                "PageIndex": index, "PageSize": self.PAGE_SIZE, "KeyWords": "", "SpecialType": 0,
                "PortalId": self.portal_id,
                "DisplayFields": ["Category", "Kind", "LocId", "PostDate", "EndTime"],
            }
            data = self.post_json(self.portal_base + self.list_path, payload, headers={
                "Referer": self.portal_base + self.list_page, "Origin": self.portal_base,
            })
            page_rows = data.get("Data") or []
            rows.extend(page_rows)
            index += 1
            total = int(data.get("Count") or 0)
            if not page_rows or len(page_rows) < self.PAGE_SIZE or len(rows) >= total:
                break

        jobs: list[InternRawJob] = []
        for row in rows:
            category = str(row.get("Category") or "")
            title = clean_text(row.get("JobAdName"))
            # 实习生招聘类别，或标题明确含“实习”（覆盖大信等把实习归入校园招聘的门户）
            if category != "实习生招聘" and "实习" not in title:
                continue
            if not title:
                continue
            locs = row.get("LocNames") or []
            city, prov = normalize_city(locs[0] if locs else "")
            end = str(row.get("EndTime") or "")
            deadline = end[:10] if end and end[:4].isdigit() and end[:10] > "2000-01-01" else UNKNOWN
            jobs.append(InternRawJob(
                title=title,
                firm_id=self.firm_id,
                firm_name=self.firm_name,
                url=f"{self.portal_base}{self.detail_path}?jobAdId={row.get('Id') or row.get('JobAdId')}",
                source_name=self.source_name,
                homepage=self.homepage,
                city=city,
                province=prov,
                published_at=str(row.get("PostDate") or "")[:10],
                deadline=deadline,
                responsibilities=clean_text(row.get("Duty"), 2400),
                requirements=clean_text(row.get("Require"), 2400),
                headcount=str(row.get("HeadCount") or "") or UNKNOWN,
                branch=clean_text(row.get("Org") or ""),
            ))
        return jobs


@register
class BDOIntern(ITalentInternCollector):
    firm_id = "bdo"
    firm_name = "立信"
    source_name = "立信官方招聘门户（bdochina.zhiye.com）"
    homepage = "https://bdochina.zhiye.com/social"
    portal_base = "https://bdochina.zhiye.com"
    portal_id = "27a38864-0636-4841-926f-a5fd0602d0bb"


@register
class TZCpaIntern(ITalentInternCollector):
    firm_id = "tzcpa"
    firm_name = "天职国际"
    source_name = "天职国际官方招聘门户（tzcpa.zhiye.com）"
    homepage = "https://tzcpa.zhiye.com/social"
    portal_base = "https://tzcpa.zhiye.com"
    portal_id = "a3718c51-2d98-462f-ab83-1e5241b8fed5"


@register
class DaXinIntern(ITalentInternCollector):
    firm_id = "daxin"
    firm_name = "大信"
    source_name = "大信官方招聘门户（daxincpa.zhiye.com）"
    homepage = "https://daxincpa.zhiye.com/social"
    portal_base = "https://daxincpa.zhiye.com"
    portal_id = "c818a775-34a5-479f-9430-f191d897af05"


@register
class ZHCpaIntern(ITalentInternCollector):
    firm_id = "zhcpa"
    firm_name = "中汇"
    source_name = "中汇官方招聘门户（zhcpa.zhiye.com）"
    homepage = "https://zhcpa.zhiye.com/social"
    portal_base = "https://zhcpa.zhiye.com"
    portal_id = "54eb3d06-fab0-49d0-8b35-59dcdb00d7d0"


@register
class GrantThorntonIntern(ITalentInternCollector):
    firm_id = "grantthornton"
    firm_name = "致同"
    source_name = "致同官方招聘门户（grantthornton.zhiye.com）"
    homepage = "https://grantthornton.zhiye.com/social"
    portal_base = "https://grantthornton.zhiye.com"
    portal_id = "ccd03e99-7a0b-4eaf-8ee5-cec9afebbe95"


@register
class DaHuaIntern(ITalentInternCollector):
    firm_id = "dahua"
    firm_name = "大华"
    source_name = "大华官方招聘门户（zhaopin.dahua-cpa.com）"
    homepage = "https://zhaopin.dahua-cpa.com/social/jobs"
    portal_base = "https://zhaopin.dahua-cpa.com"
    portal_id = "b30533ad-bc5c-47bc-87c9-53d379aed9ad"
    detail_path = "/social/detail"
    list_page = "/social/jobs"
    verify = False


@register
class ZSZHCpaIntern(ITalentInternCollector):
    firm_id = "zszh"
    firm_name = "中审众环"
    source_name = "中审众环官方招聘门户（job.zszhcpa.cn）"
    homepage = "https://job.zszhcpa.cn/jobs"
    portal_base = "https://job.zszhcpa.cn"
    portal_id = "1f2ffe4e-5fac-4629-b401-fce9a8feb7a7"


# ---------------- 天健 实习生招聘 ----------------

@register
class TianJianIntern(InternCollector):
    firm_id = "tianjian"
    firm_name = "天健"
    source_name = "天健官方招聘系统（zhaopin.pccpa.cn）"
    homepage = "https://zhaopin.pccpa.cn/hr/recruit/society"
    API = "https://zhaopin.pccpa.cn/api/hr/recruit/job/fetch/list"

    def fetch(self) -> list[InternRawJob]:
        payload = {"pageSize": 200, "pageNum": 1, "queryKey": "",
                   "selectCondition": {"jobPersonProperty": 3, "jobWorkCityList": [0], "jobStyleList": [0]}}
        data = self.post_json(self.API, payload, headers={
            "Referer": self.homepage, "Origin": "https://zhaopin.pccpa.cn"})
        if data.get("code") != 0:
            raise RuntimeError(f"接口异常：{data.get('message')}")
        rows = (data.get("data") or {}).get("rows") or []
        jobs = []
        for row in rows:
            title = clean_text(row.get("jobOutName"))
            if not title:
                continue
            jobs.append(InternRawJob(
                title=title,
                firm_id=self.firm_id,
                firm_name=self.firm_name,
                url="https://zhaopin.pccpa.cn/hr/recruit/society/detail?jobId=" + str(row.get("jobId")),
                source_name=self.source_name,
                homepage=self.homepage,
                city=clean_text(row.get("jobWorkCity")),
                branch=clean_text(row.get("areaName")),
                published_at=str(row.get("recruitStartDate") or "")[:10],
                responsibilities=clean_text(row.get("jobDuty"), 2400),
                requirements=clean_text(row.get("jobRequire"), 2400),
                headcount=str(row.get("recruitCount") or "") or UNKNOWN,
            ))
        return jobs


# ---------------- 信永中和 实习 ----------------

@register
class ShineWingIntern(InternCollector):
    firm_id = "shinewing"
    firm_name = "信永中和"
    source_name = "信永中和官方招聘系统（job.shinewing.com）"
    homepage = "https://job.shinewing.com/job/social"
    API = "https://job.shinewing.com/api/"
    PAGE_SIZE = 20
    MAX_PAGES = 12
    DETAIL_BUDGET = 100
    CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                         "data", "intern", "cache", "shinewing.json")

    def _sleep(self):
        time.sleep(0.7 + random.uniform(0, 0.4))

    def _cache_load(self):
        if os.path.exists(self.CACHE):
            try:
                with open(self.CACHE, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:  # noqa: BLE001
                return {}
        return {}

    def _cache_save(self, cache):
        os.makedirs(os.path.dirname(self.CACHE), exist_ok=True)
        with open(self.CACHE + ".tmp", "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
        os.replace(self.CACHE + ".tmp", self.CACHE)

    def fetch(self) -> list[InternRawJob]:
        rows, total = [], None
        for page_no in range(1, self.MAX_PAGES + 1):
            payload = {"position_name": "", "position_recruit": 2, "position_district": "全部",
                       "position_sector": 0, "position_status": 1, "page_no": page_no,
                       "page_size": self.PAGE_SIZE}
            data = self.post_json(self.API + "?s=App.Position.PositionList", payload,
                                  headers={"Referer": self.homepage, "Origin": "https://job.shinewing.com"})
            body = data.get("result") or data.get("data") or data
            body = body if isinstance(body, dict) else {}
            page_rows = body.get("list") or []
            if total is None:
                total = int(body.get("total") or 0)
            if not page_rows:
                break
            rows.extend(page_rows)
            if total and len(rows) >= total:
                break
            self._sleep()

        cache = self._cache_load()
        fetched = 0
        jobs = []
        for row in rows:
            title = clean_text(row.get("position_name"))
            if not title or "实习" not in title:
                continue
            pid = row.get("id")
            info = cache.get(str(pid))
            if not info and fetched < self.DETAIL_BUDGET:
                try:
                    d = self.post_json(self.API + "?s=App.Position.PositionInfo", {"id": pid},
                                       headers={"Referer": self.homepage, "Origin": "https://job.shinewing.com"})
                    info = d.get("result") or d.get("data") or d
                    fetched += 1
                    if info:
                        cache[str(pid)] = info
                    self._sleep()
                except Exception:  # noqa: BLE001
                    info = None
            item = info or row
            content = clean_text(item.get("position_content") or "", 3000)
            jobs.append(InternRawJob(
                title=title,
                firm_id=self.firm_id,
                firm_name=self.firm_name,
                url="https://job.shinewing.com/job/detail?id=" + str(pid),
                source_name=self.source_name,
                homepage=self.homepage,
                city=clean_text(item.get("position_district") or row.get("position_district")),
                published_at=str(item.get("position_start") or row.get("position_start") or "")[:10],
                headcount=str(item.get("position_num") or row.get("position_num") or "") or UNKNOWN,
                requirements=content,
                responsibilities=content,
            ))
        self._cache_save(cache)
        return jobs
