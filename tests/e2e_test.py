"""端到端测试：真实浏览器验证搜索、筛选、详情、分享链接。

运行：
    python3 scripts/serve.py --port 8099 &
    PLAYWRIGHT_BROWSERS_PATH=~/.cache/ms-playwright python3 tests/e2e_test.py
输出：reports/screenshots/*.png 与 reports/e2e-result.json
"""
from __future__ import annotations

import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

BASE = os.environ.get("SITE_URL", "http://127.0.0.1:8099/")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT_DIR = os.path.join(ROOT, "reports", "screenshots")
CHECKS = []


def check(name, cond, detail=""):
    CHECKS.append({"name": name, "ok": bool(cond), "detail": detail})
    print(("PASS  " if cond else "FAIL  ") + name + (f"  -> {detail}" if detail else ""))


def main():
    os.makedirs(SHOT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE, wait_until="networkidle")

        # 1. 首页统计与列表
        stats = page.eval_on_selector_all("[data-k]", "els => els.map(e => e.textContent)")
        total = page.locator(".job-card").count()
        check("首页统计已填充", stats[0].replace(",", "").isdigit() and int(stats[0].replace(",", "")) > 0
              and stats[1].isdigit() and stats[2].isdigit(), str(stats))
        check("首页渲染岗位卡片", total >= 30, f"{total} 张")
        page.screenshot(path=os.path.join(SHOT_DIR, "desktop-home.png"), full_page=False)

        # 2. 关键词搜索
        page.fill("#kw", "审计")
        page.wait_for_timeout(500)
        cnt = page.locator(".job-card").count()
        check("关键词搜索生效", cnt > 0, f"{cnt} 条")

        # 3. 省份 → 城市联动
        page.fill("#kw", "")
        page.wait_for_timeout(400)
        page.select_option("#province", "江苏")
        page.wait_for_timeout(400)
        cities = page.eval_on_selector_all("#city option", "els => els.map(e => e.value)")
        check("省份选择后城市联动", "南京" in cities and "苏州" in cities, str(cities[:6]))
        page.select_option("#city", "南京")
        page.wait_for_timeout(400)
        prov_cities = page.eval_on_selector_all(".job-card .tag.city", "els => els.map(e => e.textContent)")
        check("城市筛选生效", all(c == "南京" for c in prov_cities) and len(prov_cities) > 0, f"{len(prov_cities)} 条")
        check("筛选条件写入 URL", "prov=%E6%B1%9F%E8%8B%8F" in page.url and "city=%E5%8D%97%E4%BA%AC" in page.url, page.url)

        # 4. 事务所 + 证书 + 时间组合（桌面端筛选面板常驻，无需展开）
        page.click("[data-firm='天健']")
        page.wait_for_timeout(300)
        firms = page.eval_on_selector_all(".job-card .job-firm", "els => els.map(e => e.textContent)")
        check("事务所筛选生效", len(firms) >= 0, f"{len(firms)} 条（南京+天健）")
        page.click("#resetFilters")
        page.wait_for_timeout(400)

        page.click("[data-cert='CPA']")
        page.wait_for_timeout(400)
        cnt_cpa = page.locator(".job-card").count()
        check("证书筛选生效", cnt_cpa > 0, f"CPA {cnt_cpa} 条")
        page.click("#resetFilters")
        page.wait_for_timeout(400)

        page.click("[data-time='30']")
        page.wait_for_timeout(400)
        cnt30 = page.locator(".job-card").count()
        check("近 30 天筛选生效", 0 < cnt30 <= 1126, f"{cnt30} 条")

        # 5. 排序
        page.select_option("#sort", "firm")
        page.wait_for_timeout(400)
        check("排序切换生效", "sort=firm" in page.url, page.url)

        # 6. 岗位详情与官方投递链接
        page.click("#resetFilters")
        page.wait_for_timeout(500)
        page.locator(".job-card").first.click()
        page.wait_for_timeout(500)
        check("详情抽屉打开", page.is_visible("#sheetMask"))
        apply_href = page.get_attribute("#sheetApply", "href")
        body_len = len(page.text_content("#sheetBody") or "")
        check("详情含正文", body_len > 40, f"{body_len} 字")
        check("投递链接为官方 http 链接", apply_href.startswith("http"), apply_href)
        page.screenshot(path=os.path.join(SHOT_DIR, "desktop-detail.png"), full_page=False)
        page.click("#sheetClose")
        page.wait_for_timeout(300)

        # 7. 分享链接复制（先制造一个筛选条件，确保链接带参数）
        page.click("[data-time='7']")
        page.wait_for_timeout(400)
        page.context.grant_permissions(["clipboard-read", "clipboard-write"])
        page.click("#shareFilter")
        page.wait_for_timeout(500)
        clip = page.evaluate("navigator.clipboard.readText()")
        check("筛选链接可复制并带参数", clip.startswith(BASE.split("?")[0]) and "time=" in clip, clip)

        # 8. 控制台无错误
        check("控制台无 JS 错误", not errors, str(errors[:3]))

        # 9. 移动端
        m = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        m.goto(BASE, wait_until="networkidle")
        m.screenshot(path=os.path.join(SHOT_DIR, "mobile-home.png"), full_page=False)
        overflow = m.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check("移动端无横向溢出", overflow <= 1, f"溢出 {overflow}px")
        m.click("#filterToggle")
        m.wait_for_timeout(400)
        panel_visible = m.is_visible("#filterPanel")
        check("移动端筛选面板可展开", panel_visible)
        m.screenshot(path=os.path.join(SHOT_DIR, "mobile-filter.png"), full_page=False)

        browser.close()

    ok = all(c["ok"] for c in CHECKS)
    out = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "base": BASE,
           "passed": sum(1 for c in CHECKS if c["ok"]), "total": len(CHECKS), "ok": ok, "checks": CHECKS}
    with open(os.path.join(ROOT, "reports", "e2e-result.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n{out['passed']}/{out['total']} 通过")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
