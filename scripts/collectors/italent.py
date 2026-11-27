"""北森 iTalent 招聘门户通用采集器。

中审众环、中汇、天职国际、致同、立信、大华使用同一套门户，接口与字段一致，
各所只需给出域名、portalId 与详情路径。
"""
from __future__ import annotations

from .base import Collector, RawJob, register
from normalize import clean_text

PAGE_SIZE = 200


class ITalentCollector(Collector):
    portal_base = ""
    portal_id = ""
    list_path = "/api/Jobad/GetJobAdPageList"
    detail_path = "/jobs/detail"
    list_page = "/jobs"

    def fetch(self) -> list[RawJob]:
        rows: list[dict] = []
        index = 0
        while index <= 10:
            payload = {
                "PageIndex": index, "PageSize": PAGE_SIZE, "KeyWords": "", "SpecialType": 0,
                "PortalId": self.portal_id,
                "DisplayFields": ["Category", "Kind", "LocId", "PostDate", "WorkWeChatQrCode"],
            }
            data = self.post_json(self.portal_base + self.list_path, payload, headers={
                "Referer": self.portal_base + self.list_page, "Origin": self.portal_base,
            })
            page_rows = data.get("Data") or []
            rows.extend(page_rows)
            index += 1
            total = int(data.get("Count") or 0)
            if not page_rows or len(page_rows) < PAGE_SIZE or len(rows) >= total:
                break

        if not rows:
            raise RuntimeError("接口返回 0 条岗位")

        jobs: list[RawJob] = []
        for row in rows:
            category = str(row.get("Category") or "")
            if "社会招聘" not in category:
                continue  # 明确排除校招与实习
            name = clean_text(row.get("JobAdName"))
            if not name or "实习" in name:
                continue
            locs = row.get("LocNames") or []
            head = row.get("HeadCount")
            jobs.append(RawJob(
                title=name,
                url=f"{self.portal_base}{self.detail_path}?jobAdId={row.get('Id') or row.get('JobAdId')}",
                city=locs[0] if locs else "",
                published_at=str(row.get("PostDate") or "")[:10],
                responsibilities=clean_text(row.get("Duty"), 2400),
                requirements=clean_text(row.get("Require"), 2400),
                headcount=str(head) if head else "",
            ))
        return jobs


@register
class ZSZHCpa(ITalentCollector):
    firm_id = "zszh"
    firm_name = "中审众环"
    source_name = "中审众环官方招聘门户（job.zszhcpa.cn）"
    homepage = "https://job.zszhcpa.cn/jobs"
    portal_base = "https://job.zszhcpa.cn"
    portal_id = "1f2ffe4e-5fac-4629-b401-fce9a8feb7a7"


@register
class ZHCpa(ITalentCollector):
    firm_id = "zhcpa"
    firm_name = "中汇"
    source_name = "中汇官方招聘门户（zhcpa.zhiye.com）"
    homepage = "https://zhcpa.zhiye.com/social"
    portal_base = "https://zhcpa.zhiye.com"
    portal_id = "54eb3d06-fab0-49d0-8b35-59dcdb00d7d0"
    list_page = "/social"


@register
class TZCpa(ITalentCollector):
    firm_id = "tzcpa"
    firm_name = "天职国际"
    source_name = "天职国际官方招聘门户（tzcpa.zhiye.com）"
    homepage = "https://tzcpa.zhiye.com/social"
    portal_base = "https://tzcpa.zhiye.com"
    portal_id = "a3718c51-2d98-462f-ab83-1e5241b8fed5"
    list_page = "/social"


@register
class GrantThornton(ITalentCollector):
    firm_id = "grantthornton"
    firm_name = "致同"
    source_name = "致同官方招聘门户（grantthornton.zhiye.com）"
    homepage = "https://grantthornton.zhiye.com/social"
    portal_base = "https://grantthornton.zhiye.com"
    portal_id = "ccd03e99-7a0b-4eaf-8ee5-cec9afebbe95"
    list_page = "/social"


@register
class BDOChina(ITalentCollector):
    firm_id = "bdo"
    firm_name = "立信"
    source_name = "立信官方招聘门户（bdochina.zhiye.com）"
    homepage = "https://bdochina.zhiye.com/social"
    portal_base = "https://bdochina.zhiye.com"
    portal_id = "27a38864-0636-4841-926f-a5fd0602d0bb"
    list_page = "/social"


@register
class DaHua(ITalentCollector):
    firm_id = "dahua"
    firm_name = "大华"
    source_name = "大华会计师事务所官方招聘门户（zhaopin.dahua-cpa.com）"
    homepage = "https://zhaopin.dahua-cpa.com/social/jobs"
    portal_base = "https://zhaopin.dahua-cpa.com"
    portal_id = "b30533ad-bc5c-47bc-87c9-53d379aed9ad"
    detail_path = "/social/detail"
    list_page = "/social/jobs"
    verify = False
