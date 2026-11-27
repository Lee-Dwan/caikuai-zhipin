"""采集器基类与注册表。

新增事务所只需：
1. 在 collectors/ 下新建 <firm_id>.py；
2. 继承 Collector，实现 fetch() 返回 RawJob 列表；
3. 用 @register 装饰。
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


@dataclass
class RawJob:
    title: str
    url: str
    city: str = ""
    province: str = ""
    category: str = ""
    published_at: str = ""
    branch: str = ""
    headcount: str = ""
    responsibilities: str = ""
    requirements: str = ""
    summary: str = ""
    employment_type: str = "社招"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectResult:
    firm_id: str
    firm_name: str
    ok: bool
    jobs: list[RawJob] = field(default_factory=list)
    error: str = ""
    pages: int = 0
    note: str = ""
    duration: float = 0.0

    def to_report(self) -> dict:
        return {"firm_id": self.firm_id, "firm_name": self.firm_name, "ok": self.ok,
                "count": len(self.jobs), "error": self.error, "pages": self.pages,
                "note": self.note, "duration": round(self.duration, 1)}


class Collector:
    firm_id: str = "unknown"
    firm_name: str = "未命名事务所"
    source_name: str = ""
    homepage: str = ""
    enabled: bool = True
    verify: bool = True
    expect_jobs: bool = True

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        })

    def get(self, url: str, **kwargs):
        kwargs.setdefault("timeout", 25)
        kwargs.setdefault("headers", {})
        last = None
        for i in range(3):
            try:
                r = self.session.get(url, verify=self.verify, **kwargs)
                if r.status_code in (200, 201, 202):
                    r.encoding = r.apparent_encoding or "utf-8"
                    return r
                last = RuntimeError(f"HTTP {r.status_code} {url}")
                if r.status_code in (403, 404, 410):
                    break
            except Exception as e:  # noqa: BLE001
                last = e
            time.sleep(1.2 * (i + 1) + random.uniform(0, 0.6))
        raise RuntimeError(str(last) if last else f"request failed: {url}")

    def get_json(self, url: str, **kwargs):
        return self.get(url, **kwargs).json()

    def post_json(self, url: str, payload: dict, **kwargs):
        last = None
        for i in range(3):
            try:
                r = self.session.post(url, json=payload, timeout=25, verify=self.verify, **kwargs)
                if r.status_code < 400:
                    return r.json()
                last = RuntimeError(f"HTTP {r.status_code} {url}")
                if r.status_code in (403, 404):
                    break
            except Exception as e:  # noqa: BLE001
                last = e
            time.sleep(1.2 * (i + 1) + random.uniform(0, 0.5))
        raise RuntimeError(str(last) if last else f"post failed: {url}")

    def fetch(self) -> list[RawJob]:
        raise NotImplementedError

    def run(self) -> CollectResult:
        t0 = time.time()
        try:
            jobs = self.fetch()
            ok = bool(jobs) or not self.expect_jobs
            note = "" if jobs else ("本次未发现社招岗位（官网正常返回）" if ok else "官网未返回岗位列表")
            return CollectResult(self.firm_id, self.firm_name, ok, jobs,
                                 "" if ok else note, note=note, duration=time.time() - t0)
        except Exception as e:  # noqa: BLE001
            return CollectResult(self.firm_id, self.firm_name, False, [],
                                 f"{type(e).__name__}: {e}", duration=time.time() - t0)


REGISTRY: dict[str, Collector] = {}


def register(obj):
    collector = obj() if isinstance(obj, type) else obj
    REGISTRY[collector.firm_id] = collector
    return obj


def all_collectors():
    return sorted(REGISTRY.values(), key=lambda c: c.firm_id)
