"""天健会计师事务所社会招聘采集器。

来源：天健官方招聘系统 https://zhaopin.pccpa.cn/hr/recruit/society
接口：POST /api/hr/recruit/job/fetch/list（公开接口，返回社招岗位全量）
"""
from __future__ import annotations

from .base import Collector, RawJob, register
from normalize import clean_text


@register
class TianJian(Collector):
    firm_id = "tianjian"
    firm_name = "天健"
    source_name = "天健官方招聘系统（zhaopin.pccpa.cn）"
    homepage = "https://zhaopin.pccpa.cn/hr/recruit/society"
    API = "https://zhaopin.pccpa.cn/api/hr/recruit/job/fetch/list"

    def fetch(self) -> list[RawJob]:
        payload = {"pageSize": 200, "pageNum": 1, "queryKey": "",
                   "selectCondition": {"jobPersonProperty": 1, "jobWorkCityList": [0], "jobStyleList": [0]}}
        data = self.post_json(self.API, payload, headers={
            "Referer": self.homepage, "Origin": "https://zhaopin.pccpa.cn"})
        if data.get("code") != 0:
            raise RuntimeError(f"接口异常：{data.get('message')}")
        rows = (data.get("data") or {}).get("rows") or []
        if not rows:
            raise RuntimeError("接口返回 0 条岗位")

        jobs = []
        for row in rows:
            if row.get("jobPersonPropertyName") and row["jobPersonPropertyName"] != "社会招聘":
                continue
            title = clean_text(row.get("jobOutName"))
            if not title:
                continue
            jobs.append(RawJob(
                title=title,
                url="https://zhaopin.pccpa.cn/hr/recruit/society/detail?jobId=" + str(row.get("jobId")),
                city=clean_text(row.get("jobWorkCity")),
                branch=clean_text(row.get("areaName")),
                category=clean_text(row.get("jobStyleName")),
                published_at=str(row.get("recruitStartDate") or "")[:10],
                headcount=str(row.get("recruitCount") or ""),
                responsibilities=clean_text(row.get("jobDuty"), 2400),
                requirements=clean_text(row.get("jobRequire"), 2400),
            ))
        return jobs
