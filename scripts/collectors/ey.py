"""安永（EY）社会招聘采集器。

来源：EY 全球招聘站 Taleo 门户 https://careers.ey.com/ey/search/?locationsearch=China
列表页每页 25 条（tr.data-row），详情页含 Schema.org 微数据（datePosted / description）。
覆盖：中国大陆 + 香港/澳门（含少量台湾地区岗位，按官方原始地点如实标注）。
"""
from __future__ import annotations

import json
import os
import re
import time

from bs4 import BeautifulSoup

from .base import Collector, RawJob, register
from normalize import clean_text

LIST = "https://careers.ey.com/ey/search/?q=&locationsearch=China&startrow={start}"
CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "cache", "ey.json")
DETAIL_BASE = "https://careers.ey.com"
EN_CITY = {
    "Hong Kong": "香港", "Macau": "澳门", "Macao": "澳门", "Beijing": "北京", "Shanghai": "上海",
    "Shenzhen": "深圳", "Guangzhou": "广州", "Hangzhou": "杭州", "Nanjing": "南京", "Suzhou": "苏州",
    "Chengdu": "成都", "Wuhan": "武汉", "Xiamen": "厦门", "Tianjin": "天津", "Chongqing": "重庆",
    "Taipei City": "台北", "Taipei": "台北", "New Taipei City": "新北", "Hsinchu City": "新竹",
    "Taichung City": "台中", "Taichung": "台中", "Tainan City": "台南", "Kaohsiung City": "高雄",
    "Kaohsiung": "高雄", "Taoyuan City": "桃园",
}


@register
class EY(Collector):
    firm_id = "ey"
    firm_name = "安永"
    source_name = "安永官方招聘站（careers.ey.com）"
    homepage = "https://careers.ey.com/ey/search/?locationsearch=China"
    MAX_PAGES = 6
    DETAIL_LIMIT = 90   # 单轮最多补抓的新岗位详情

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

    def parse_list(self) -> list[dict]:
        rows, seen = [], set()
        for page in range(self.MAX_PAGES):
            r = self.get(LIST.format(start=page * 25))
            soup = BeautifulSoup(r.text, "lxml")
            items = soup.select("tr.data-row")
            if not items:
                break
            for it in items:
                link = it.select_one("a.jobTitle-link")
                if not link:
                    continue
                href = link.get("href") or ""
                url = href if href.startswith("http") else DETAIL_BASE + href
                key = url.split("?")[0]
                if key in seen:
                    continue
                seen.add(key)
                loc = it.select_one(".jobLocation") or it.select_one(".job-location")
                rows.append({"title": clean_text(link.get_text()),
                             "url": url,
                             "location": clean_text(loc.get_text()) if loc else ""})
            if len(items) < 20:
                break
        return rows

    def city_from_location(self, raw: str) -> str:
        if not raw:
            return ""
        raw = re.sub(r"\+\d+\s*more.*$", "", raw).strip()
        for seg in [s.strip() for s in raw.split(",")]:
            for sub in seg.split("/"):
                sub = sub.strip()
                if re.search(r"[\u4e00-\u9fa5]", sub):
                    sub = re.sub(r"(特别行政区|维吾尔自治区|壮族自治区|回族自治区|自治区|省|市)$", "", sub)
                    return sub
        head = raw.split(",")[0].strip()
        return EN_CITY.get(head, head if re.search(r"[\u4e00-\u9fa5]", head) else "")

    def fetch(self) -> list[RawJob]:
        rows = self.parse_list()
        if not rows:
            raise RuntimeError("列表页未解析到岗位（页面结构可能变化）")

        cache = self.load_cache()
        jobs, fetched = [], 0
        for row in rows:
            key = row["url"].split("?")[0]
            item = cache.get(key)
            if item:
                if item.get("location"):
                    row["location"] = item["location"]
                jobs.append(RawJob(title=row["title"], url=row["url"],
                                   city=self.city_from_location(row["location"]),
                                   published_at=item.get("published_at", ""),
                                   responsibilities=item.get("duty", ""),
                                   requirements=item.get("req", "")))
                continue
            published = desc = req = ""
            if fetched < self.DETAIL_LIMIT:
                try:
                    fetched += 1
                    d = self.get(row["url"])
                    soup = BeautifulSoup(d.text, "lxml")
                    meta = soup.find("meta", attrs={"itemprop": "datePosted"})
                    if meta and meta.get("content"):
                        published = self._parse_date(meta["content"])
                    node = soup.find(attrs={"itemprop": "description"})
                    if node:
                        text = clean_text(node.get_text("\n"), 3000)
                        desc, req = self._split(text)
                    loc = soup.find("meta", attrs={"itemprop": "streetAddress"})
                    if loc and loc.get("content"):
                        row["location"] = loc["content"]
                    cache[key] = {"published_at": published, "duty": desc, "req": req,
                                  "location": row["location"]}
                    time.sleep(0.4)
                except Exception:  # noqa: BLE001
                    pass
            jobs.append(RawJob(
                title=row["title"],
                url=row["url"],
                city=self.city_from_location(row["location"]),
                published_at=published,
                responsibilities=desc,
                requirements=req,
            ))
        self.save_cache(cache)
        return jobs

    @staticmethod
    def _split(text: str):
        if not text:
            return "", ""
        m = re.search(r"(任职资格|任职要求|资格要求|岗位要求|Qualifications|Requirements)", text)
        if m and m.start() > 20:
            return text[:m.start()].strip(), text[m.start():].strip()
        return text, ""

    @staticmethod
    def _parse_date(raw: str) -> str:
        m = re.search(r"(\d{1,2}) (\w{3}) (\d{4})", raw)
        if m:
            months = {name: i for i, name in enumerate(
                ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
            mon = months.get(m.group(2), 0)
            if mon:
                return f"{m.group(3)}-{mon:02d}-{int(m.group(1)):02d}"
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
        return m.group(0) if m else ""
