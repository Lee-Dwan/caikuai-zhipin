"""容诚会计师事务所社会招聘采集器。

来源：https://careers.rccpa.com.cn/#/home（Vue 单页应用）
接口：GET /eRecruit/recruit/position/getIndexPositions?type=2（type=2 为社会招聘）
说明：该站岗位详情为页面内弹层，无独立详情 URL，投递链接统一指向官方招聘首页。
"""
from __future__ import annotations

import re

from .base import Collector, RawJob, register
from normalize import clean_text


@register
class RongCheng(Collector):
    firm_id = "rongcheng"
    firm_name = "容诚"
    source_name = "容诚官方招聘门户（careers.rccpa.com.cn）"
    homepage = "https://careers.rccpa.com.cn/#/home"
    API = "https://careers.rccpa.com.cn/eRecruit/recruit/position/getIndexPositions?type=2&titleSite="

    def fetch(self) -> list[RawJob]:
        data = self.get_json(self.API, headers={"Referer": self.homepage})
        payload = data.get("data") if isinstance(data, dict) else data
        rows = payload if isinstance(payload, list) else (payload or {}).get("list") or []
        if not rows:
            raise RuntimeError("接口返回 0 条岗位")

        jobs = []
        for row in rows:
            title = clean_text(row.get("title") or row.get("positionName"))
            if not title or "实习" in title:
                continue
            if str(row.get("status")) not in ("Y", "1", "None"):
                continue
            place = clean_text(row.get("workPlaceT") or "")
            city, head = "", ""
            if place:
                part = place.split(",")[0]
                seg = re.split(r"[:：]", part)
                city = seg[0].strip()
                if len(seg) > 1:
                    num = re.sub(r"[^0-9]", "", seg[1])
                    head = num
            text = clean_text(row.get("requirement"), 4000)
            duty, req = self._split(text)
            jobs.append(RawJob(
                title=title,
                url=self.homepage,   # 无独立详情页，指向官方门户首页
                city=city,
                published_at=self._date(row.get("updateTime") or row.get("createTime")),
                headcount=head,
                responsibilities=duty,
                requirements=req,
            ))
        return jobs

    @staticmethod
    def _date(raw) -> str:
        s = str(raw or "")
        m = re.match(r"(\d{4})(\d{2})(\d{2})", s)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
        return m.group(0) if m else ""

    @staticmethod
    def _split(text: str):
        if not text:
            return "", ""
        m = re.search(r"(任职要求|任职资格|岗位要求|任职条件|职位要求)", text)
        if m and m.start() > 10:
            duty = re.sub(r"^(岗位职责|职位职责|职位描述|工作职责)[:：]\s*", "", text[:m.start()].strip())
            return duty, text[m.start():].strip()
        return re.sub(r"^(岗位职责|职位职责|职位描述|工作职责)[:：]\s*", "", text), ""
