"""信永中和社会招聘采集器。

来源：https://job.shinewing.com/job/social
列表接口 POST /api/?s=App.Position.PositionList（page_size 最大 20，total 约 218）
详情接口 POST /api/?s=App.Position.PositionInfo（position_content 合并了职责与要求）
该站详情接口对高频请求敏感：详情走本地缓存，仅对新 id 请求，每次间隔约 1 秒。
"""
from __future__ import annotations

import json
import os
import random
import re
import time

from .base import Collector, RawJob, register
from normalize import clean_text

CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                          "data", "cache", "shinewing.json")


@register
class ShineWing(Collector):
    firm_id = "shinewing"
    firm_name = "信永中和"
    source_name = "信永中和官方招聘系统（job.shinewing.com）"
    homepage = "https://job.shinewing.com/job/social"
    API = "https://job.shinewing.com/api/"
    PAGE_SIZE = 20
    MAX_PAGES = 12
    DETAIL_BUDGET = 70

    def _sleep(self):
        time.sleep(0.8 + random.uniform(0, 0.5))

    def load_cache(self) -> dict:
        path = os.path.normpath(CACHE_PATH)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:  # noqa: BLE001
                return {}
        return {}

    def save_cache(self, cache: dict) -> None:
        path = os.path.normpath(CACHE_PATH)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
        os.replace(path + ".tmp", path)

    def list_page(self, page_no: int) -> dict:
        payload = {"position_name": "", "position_recruit": 1, "position_district": "全部",
                   "position_sector": 0, "position_status": 1, "page_no": page_no,
                   "page_size": self.PAGE_SIZE}
        data = self.post_json(self.API + "?s=App.Position.PositionList", payload,
                              headers={"Referer": self.homepage, "Origin": "https://job.shinewing.com"})
        body = data.get("result") or data.get("data") or data
        return body if isinstance(body, dict) else {}

    def detail(self, pid) -> dict:
        data = self.post_json(self.API + "?s=App.Position.PositionInfo", {"id": pid},
                              headers={"Referer": self.homepage, "Origin": "https://job.shinewing.com"})
        body = data.get("result") or data.get("data") or data
        return body if isinstance(body, dict) else {}

    def fetch(self) -> list[RawJob]:
        cache = self.load_cache()
        rows, total = [], None
        for page_no in range(1, self.MAX_PAGES + 1):
            body = self.list_page(page_no)
            page_rows = body.get("list") or []
            if total is None:
                total = int(body.get("total") or 0)
            if not page_rows:
                break
            rows.extend(page_rows)
            if total and len(rows) >= total:
                break
            self._sleep()

        if not rows:
            raise RuntimeError("列表接口返回 0 条岗位")

        fetched = 0
        jobs = []
        for row in rows:
            pid = row.get("id")
            if pid is None:
                continue
            item = cache.get(str(pid))
            if not item and fetched < self.DETAIL_BUDGET:
                try:
                    item = self.detail(pid)
                    fetched += 1
                    if item:
                        cache[str(pid)] = item
                    self._sleep()
                except Exception:  # noqa: BLE001
                    item = None
            info = item or row
            title = clean_text(info.get("position_name") or row.get("position_name"))
            if not title or "实习" in title:
                continue
            content = clean_text(info.get("position_content"), 4000)
            duty, req = self._split(content)
            jobs.append(RawJob(
                title=title,
                url="https://job.shinewing.com/job/detail?id=" + str(pid),
                city=clean_text(info.get("position_district") or row.get("position_district")),
                published_at=str(info.get("position_start") or row.get("position_start") or "")[:10],
                headcount=str(info.get("position_num") or row.get("position_num") or ""),
                responsibilities=duty,
                requirements=req,
            ))
        self.save_cache(cache)
        return jobs

    @staticmethod
    def _split(text: str):
        if not text:
            return "", ""
        m = re.search(r"(任职资格|任职要求|岗位要求|任职条件|职位要求)", text)
        if m and m.start() > 15:
            duty = re.sub(r"^(岗位职责|职位职责|职位描述|工作职责|主要职责)[:：]\s*", "", text[:m.start()].strip())
            return duty, text[m.start():].strip()
        return re.sub(r"^(岗位职责|职位职责|职位描述|工作职责)[:：]\s*", "", text), ""
