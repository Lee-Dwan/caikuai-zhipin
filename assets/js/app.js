/* 确实在审 — 前端逻辑（无依赖，移动优先） */
(function () {
  "use strict";

  var state = {
    data: null,
    jobs: [],
    filters: { q: "", prov: "", city: "", firms: [], cats: [], certs: [], time: "all", sort: "new" },
    page: 1, pageSize: 30, filtered: []
  };

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var PROVINCE_ORDER = ["北京","上海","天津","重庆","广东","江苏","浙江","山东","福建","四川","湖北","湖南","河南","河北","安徽","江西","陕西","山西","辽宁","吉林","黑龙江","云南","贵州","广西","海南","内蒙古","甘肃","青海","宁夏","新疆","西藏","香港","澳门","台湾"];
  var HOT_CITIES = ["北京","上海","深圳","广州","杭州","南京","苏州","成都","武汉","西安","重庆","天津","长沙","合肥","济南","无锡","厦门","郑州"];

  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function todayStr() { var d = new Date(); return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); }
  function parseDate(s) {
    if (!s) return null;
    var m = String(s).match(/(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/);
    return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
  }
  function daysBetween(a, b) {
    if (!a) return 9999;
    return Math.round((new Date(b.getFullYear(), b.getMonth(), b.getDate()) - new Date(a.getFullYear(), a.getMonth(), a.getDate())) / 86400000);
  }
  function relDate(s) {
    var d = parseDate(s);
    if (!d) return "时间待核";
    var diff = daysBetween(d, new Date());
    if (diff <= 0) return "今天发布";
    if (diff === 1) return "昨天发布";
    if (diff <= 30) return diff + " 天前发布";
    return (d.getMonth() + 1) + "月" + d.getDate() + "日发布";
  }
  function fmtTime(iso) {
    if (!iso) return "–";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
  }

  function loadData() {
    return fetch("data/jobs.json", { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).catch(function () {
      return new Promise(function (resolve, reject) {
        var s = document.createElement("script");
        s.src = "assets/js/data-fallback.js";
        s.onload = function () { window.__JOBS_DATA ? resolve(window.__JOBS_DATA) : reject(new Error("fallback empty")); };
        s.onerror = function () { reject(new Error("数据读取失败")); };
        document.head.appendChild(s);
      });
    });
  }

  function boot(data) {
    state.data = data || {};
    state.jobs = (state.data.jobs || []).filter(function (j) { return j && j.status !== "closed"; });
    renderHeader();
    buildFilters();
    readURL();
    applyAll();
    bindEvents();
  }

  function renderHeader() {
    var meta = state.data.meta || {};
    var jobs = state.jobs;
    var today = todayStr();
    var todayCount = (meta.today_new != null) ? meta.today_new : jobs.filter(function (j) {
      return String(j.published_at || "").slice(0, 10) === today || String(j.first_seen || "").slice(0, 10) === today;
    }).length;
    var firmSet = {};
    jobs.forEach(function (j) { firmSet[j.firm_id || j.firm] = 1; });
    var firmCount = Object.keys(firmSet).length;
    var set = function (k, v) { var el = $('[data-k="' + k + '"]'); if (el) el.textContent = v; };
    set("activeJobs", jobs.length.toLocaleString());
    set("firms", firmCount);
    set("today", todayCount);
    set("updated", fmtTime(meta.generated_at));
    $("#headerUpdate").textContent = meta.generated_at ? "更新 " + fmtTime(meta.generated_at) : "等待更新";
    $("#footerUpdate").textContent = "最近更新：" + (meta.generated_at ? fmtTime(meta.generated_at) : "–");
    $("#year").textContent = new Date().getFullYear();

    var health = (meta.firms_status || []).filter(function (f) { return f.status === "failed"; });
    var bar = $("#healthBar");
    if (health.length) {
      var names = health.map(function (f) { return f.name; }).join("、");
      bar.innerHTML = '<div class="wrap"><span>⚠️</span><span><b>采集提示：</b>' + esc(names) +
        " 本次更新未成功，页面保留其历史岗位，未判定为下架。数据以官方页面为准。</span></div>";
      bar.hidden = false;
    } else { bar.hidden = true; }
  }

  function buildFilters() {
    var provs = {}, cities = {}, firms = {}, cats = {}, certs = {};
    state.jobs.forEach(function (j) {
      if (j.province) provs[j.province] = (provs[j.province] || 0) + 1;
      if (j.city) cities[j.city] = (cities[j.city] || 0) + 1;
      if (j.firm) firms[j.firm] = (firms[j.firm] || 0) + 1;
      if (j.category) cats[j.category] = (cats[j.category] || 0) + 1;
      (j.certs || []).forEach(function (c) { certs[c] = (certs[c] || 0) + 1; });
    });

    $("#province").innerHTML = '<option value="">全部省份</option>' + Object.keys(provs).sort(function (a, b) {
      var ia = PROVINCE_ORDER.indexOf(a), ib = PROVINCE_ORDER.indexOf(b);
      if (ia < 0) ia = 99; if (ib < 0) ib = 99;
      return ia - ib || a.localeCompare(b, "zh");
    }).map(function (p) { return '<option value="' + esc(p) + '">' + esc(p) + "（" + provs[p] + "）</option>"; }).join("");

    $("#firmChips").innerHTML = Object.keys(firms).sort(function (a, b) { return firms[b] - firms[a]; }).map(function (f) {
      return '<button type="button" class="chip sm" data-firm="' + esc(f) + '">' + esc(f) + '<span style="opacity:.55;margin-left:4px">' + firms[f] + "</span></button>";
    }).join("");

    var catOrder = ["审计", "税务", "咨询", "评估", "工程造价", "其他"];
    $("#catChips").innerHTML = Object.keys(cats).sort(function (a, b) { return catOrder.indexOf(a) - catOrder.indexOf(b); }).map(function (c) {
      return '<button type="button" class="chip sm" data-cat="' + esc(c) + '">' + esc(c) + "</button>";
    }).join("");

    var certOrder = ["CPA", "税务师", "中级会计师", "ACCA", "其他证书", "不限"];
    $("#certChips").innerHTML = Object.keys(certs).sort(function (a, b) { return certOrder.indexOf(a) - certOrder.indexOf(b); }).map(function (c) {
      return '<button type="button" class="chip sm" data-cert="' + esc(c) + '">' + esc(c) + '<span style="opacity:.55;margin-left:4px">' + certs[c] + "</span></button>";
    }).join("");

    $("#hotCities").innerHTML = HOT_CITIES.filter(function (c) { return cities[c]; }).map(function (c) {
      return '<button type="button" class="chip sm" data-city="' + esc(c) + '">' + esc(c) + '<span style="opacity:.55;margin-left:4px">' + cities[c] + "</span></button>";
    }).join("");
  }

  function refreshCityOptions() {
    var prov = state.filters.prov, pools = {};
    state.jobs.forEach(function (j) {
      if (!j.city || (prov && j.province !== prov)) return;
      pools[j.city] = (pools[j.city] || 0) + 1;
    });
    var sel = $("#city"), cur = state.filters.city;
    sel.innerHTML = '<option value="">全部城市</option>' + Object.keys(pools).sort(function (a, b) { return pools[b] - pools[a]; }).map(function (c) {
      return '<option value="' + esc(c) + '">' + esc(c) + "（" + pools[c] + "）</option>";
    }).join("");
    if (cur && pools[cur]) sel.value = cur; else if (cur) state.filters.city = "";
  }

  function matchTime(j) {
    var t = state.filters.time;
    if (t === "all") return true;
    var d = parseDate(j.published_at) || parseDate(j.first_seen);
    if (!d) return false;
    var diff = daysBetween(d, new Date());
    if (t === "today") return diff === 0;
    return diff >= 0 && diff <= Number(t);
  }

  function applyAll(resetPage) {
    if (resetPage !== false) state.page = 1;
    var f = state.filters, q = f.q.trim().toLowerCase(), terms = q ? q.split(/\s+/) : [];
    state.filtered = state.jobs.filter(function (j) {
      if (f.prov && j.province !== f.prov) return false;
      if (f.city && j.city !== f.city) return false;
      if (f.firms.length && f.firms.indexOf(j.firm) < 0) return false;
      if (f.cats.length && f.cats.indexOf(j.category) < 0) return false;
      if (f.certs.length && !f.certs.some(function (c) { return (j.certs || []).indexOf(c) >= 0; })) return false;
      if (!matchTime(j)) return false;
      if (terms.length) {
        var hay = [j.title, j.firm, j.city, j.province, j.category, (j.certs || []).join(" "), j.summary, j.requirements].join(" ").toLowerCase();
        for (var i = 0; i < terms.length; i++) if (hay.indexOf(terms[i]) < 0) return false;
      }
      return true;
    });
    sortJobs();
    renderList();
    renderActiveFilters();
    syncURL();
    updateFilterBadge();
  }

  function sortJobs() {
    var s = state.filters.sort;
    state.filtered.sort(function (a, b) {
      if (s === "firm") return String(a.firm).localeCompare(String(b.firm), "zh") || cmpDate(a, b);
      if (s === "city") return String(a.city).localeCompare(String(b.city), "zh") || cmpDate(a, b);
      return cmpDate(a, b);
    });
  }
  function cmpDate(a, b) {
    return (parseDate(b.published_at) || new Date(0)) - (parseDate(a.published_at) || new Date(0));
  }

  function renderList() {
    var list = $("#list"), total = state.filtered.length, shown = Math.min(total, state.page * state.pageSize);
    $("#resultCount").innerHTML = total ? "共 <b>" + total + "</b> 个在招岗位" + (total > shown ? "，已显示 " + shown + " 个" : "") : "";
    if (!total) {
      list.innerHTML = ""; $("#empty").hidden = false; $("#loadMore").hidden = true;
      $("#resultCount").textContent = "没有匹配的岗位";
      return;
    }
    $("#empty").hidden = true;
    list.innerHTML = state.filtered.slice(0, shown).map(cardHTML).join("");
    $("#loadMore").hidden = shown >= total;
    $("#loadMore").textContent = "加载更多岗位（还有 " + (total - shown) + " 个）";
  }

  function cardHTML(j) {
    var meta = (state.data && state.data.meta) || {};
    var isNew = meta.baseline_at !== todayStr() && daysBetween(parseDate(j.first_seen), new Date()) <= 2;
    var certs = (j.certs || []).filter(function (c) { return c && c !== "不限"; });
    return '<article class="job-card" data-id="' + esc(j.id) + '">' +
      '<div class="job-top"><div style="min-width:0">' +
        '<h2 class="job-title">' + esc(j.title) + (isNew ? '<span class="new-dot">NEW</span>' : "") + "</h2>" +
        '<div class="job-firm"><span class="firm-logo">' + esc((j.firm || "?").slice(0, 1)) + "</span>" + esc(j.firm) + "</div>" +
      "</div>" +
      '<span class="job-date">' + esc(relDate(j.published_at)) + "</span></div>" +
      '<div class="job-meta">' +
        (j.city ? '<span class="tag city">' + esc(j.city) + "</span>" : "") +
        (j.category ? '<span class="tag cat">' + esc(j.category) + "</span>" : "") +
        certs.slice(0, 3).map(function (c) { return '<span class="tag cert">' + esc(c) + "</span>"; }).join("") +
      "</div>" +
      (j.summary ? '<p class="job-req">' + esc(j.summary) + "</p>" : "") +
      '<div class="job-actions"><span class="src-note">官方来源</span>' +
        '<button class="btn sm ghost" type="button" data-act="detail">详情</button>' +
        '<a class="btn sm primary" href="' + esc(j.url || "#") + '" target="_blank" rel="noopener nofollow" data-act="apply">官方投递</a>' +
      "</div></article>";
  }

  function renderActiveFilters() {
    var f = state.filters, parts = [];
    if (f.q) parts.push(pill("关键词：" + f.q, "q"));
    if (f.prov) parts.push(pill(f.prov, "prov"));
    if (f.city) parts.push(pill(f.city, "city"));
    f.firms.forEach(function (x) { parts.push(pill(x, "firm|" + x)); });
    f.cats.forEach(function (x) { parts.push(pill(x, "cat|" + x)); });
    f.certs.forEach(function (x) { parts.push(pill(x, "cert|" + x)); });
    if (f.time !== "all") parts.push(pill({ today: "今日新增", "7": "近 7 天", "30": "近 30 天" }[f.time], "time"));
    var box = $("#activeFilters");
    box.innerHTML = parts.join("");
    box.hidden = parts.length === 0;
  }
  function pill(text, key) { return '<span class="pill">' + esc(text) + '<button type="button" data-rm="' + esc(key) + '" aria-label="移除">×</button></span>'; }

  function updateFilterBadge() {
    var f = state.filters;
    var n = (f.prov ? 1 : 0) + (f.city ? 1 : 0) + f.firms.length + f.cats.length + f.certs.length + (f.time !== "all" ? 1 : 0);
    $("#filterCount").textContent = n;
    $("#filterCount").hidden = n === 0;
    $$("#timeRow .chip").forEach(function (c) { c.classList.toggle("on", c.dataset.time === f.time); });
  }

  function syncURL() {
    var f = state.filters, p = new URLSearchParams();
    if (f.q) p.set("q", f.q);
    if (f.prov) p.set("prov", f.prov);
    if (f.city) p.set("city", f.city);
    if (f.firms.length) p.set("firms", f.firms.join(","));
    if (f.cats.length) p.set("cats", f.cats.join(","));
    if (f.certs.length) p.set("certs", f.certs.join(","));
    if (f.time !== "all") p.set("time", f.time);
    if (f.sort !== "new") p.set("sort", f.sort);
    var qs = p.toString();
    try { history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash); } catch (e) {}
  }

  function readURL() {
    var p = new URLSearchParams(location.search), f = state.filters;
    f.q = p.get("q") || "";
    f.prov = p.get("prov") || "";
    f.city = p.get("city") || "";
    f.firms = (p.get("firms") || "").split(",").filter(Boolean);
    f.cats = (p.get("cats") || "").split(",").filter(Boolean);
    f.certs = (p.get("certs") || "").split(",").filter(Boolean);
    f.time = p.get("time") || "all";
    f.sort = p.get("sort") || "new";
    $("#kw").value = f.q;
    $("#province").value = f.prov;
    refreshCityOptions();
    $("#city").value = f.city;
    $("#sort").value = f.sort;
    $$("[data-firm]").forEach(function (c) { c.classList.toggle("on", f.firms.indexOf(c.dataset.firm) >= 0); });
    $$("[data-cat]").forEach(function (c) { c.classList.toggle("on", f.cats.indexOf(c.dataset.cat) >= 0); });
    $$("[data-cert]").forEach(function (c) { c.classList.toggle("on", f.certs.indexOf(c.dataset.cert) >= 0); });
  }

  function bindEvents() {
    var t = null;
    $("#kw").addEventListener("input", function (e) {
      $("#clearKw").hidden = !e.target.value;
      clearTimeout(t);
      t = setTimeout(function () { state.filters.q = e.target.value; applyAll(); }, 220);
    });
    $("#kw").addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); state.filters.q = e.target.value; applyAll(); e.target.blur(); }
    });
    $("#clearKw").addEventListener("click", function () { $("#kw").value = ""; state.filters.q = ""; this.hidden = true; applyAll(); });
    $("#timeRow").addEventListener("click", function (e) {
      var b = e.target.closest("[data-time]");
      if (!b) return;
      state.filters.time = b.dataset.time;
      applyAll();
    });
    $("#filterToggle").addEventListener("click", function () {
      var open = $("#filterPanel").classList.toggle("open");
      this.setAttribute("aria-expanded", open ? "true" : "false");
    });
    $("#province").addEventListener("change", function () {
      state.filters.prov = this.value; state.filters.city = "";
      refreshCityOptions(); applyAll();
    });
    $("#city").addEventListener("change", function () { state.filters.city = this.value; applyAll(); });
    document.addEventListener("click", function (e) {
      var f = e.target.closest("[data-firm]");
      if (f) { toggleIn(state.filters.firms, f.dataset.firm); f.classList.toggle("on"); applyAll(); return; }
      var c = e.target.closest("[data-cat]");
      if (c) { toggleIn(state.filters.cats, c.dataset.cat); c.classList.toggle("on"); applyAll(); return; }
      var ce = e.target.closest("[data-cert]");
      if (ce) { toggleIn(state.filters.certs, ce.dataset.cert); ce.classList.toggle("on"); applyAll(); return; }
      var ct = e.target.closest("[data-city]");
      if (ct) {
        var v = ct.dataset.city;
        state.filters.city = state.filters.city === v ? "" : v;
        $("#city").value = state.filters.city;
        $$("[data-city]").forEach(function (x) { x.classList.toggle("on", x.dataset.city === state.filters.city); });
        applyAll(); return;
      }
      var rm = e.target.closest("[data-rm]");
      if (rm) removeFilter(rm.dataset.rm);
    });
    $("#resetFilters").addEventListener("click", resetAll);
    $("#emptyReset").addEventListener("click", resetAll);
    $("#applyFilters").addEventListener("click", function () {
      applyAll();
      $("#filterPanel").classList.remove("open");
      $("#filterToggle").setAttribute("aria-expanded", "false");
      document.querySelector(".results").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    $("#sort").addEventListener("change", function () { state.filters.sort = this.value; applyAll(false); });
    $("#loadMore").addEventListener("click", function () { state.page++; renderList(); });
    $("#list").addEventListener("click", function (e) {
      var card = e.target.closest(".job-card");
      if (!card || e.target.closest("[data-act='apply']")) return;
      openSheet(card.dataset.id);
    });
    $("#shareTop").addEventListener("click", sharePage);
    $("#shareFilter").addEventListener("click", sharePage);
    $("#sheetClose").addEventListener("click", closeSheet);
    $("#sheetMask").addEventListener("click", function (e) { if (e.target === this) closeSheet(); });
    $("#sheetShare").addEventListener("click", function () {
      var id = $("#sheetMask").dataset.id;
      copyText(location.origin + location.pathname + "?job=" + encodeURIComponent(id)).then(function (ok) {
        toast(ok ? "岗位链接已复制，可直接发到微信" : "复制失败，请手动复制地址栏");
      });
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeSheet(); });
    var pending = new URLSearchParams(location.search).get("job");
    if (pending) setTimeout(function () { openSheet(pending); }, 200);
  }

  function toggleIn(a, v) { var i = a.indexOf(v); if (i >= 0) a.splice(i, 1); else a.push(v); }

  function removeFilter(key) {
    if (key === "q") { state.filters.q = ""; $("#kw").value = ""; $("#clearKw").hidden = true; }
    else if (key === "prov") { state.filters.prov = ""; $("#province").value = ""; refreshCityOptions(); }
    else if (key === "city") { state.filters.city = ""; $("#city").value = ""; $$("[data-city]").forEach(function (x) { x.classList.remove("on"); }); }
    else if (key === "time") state.filters.time = "all";
    else {
      var p = key.split("|"), map = { firm: ["firms", "[data-firm]", "firm"], cat: ["cats", "[data-cat]", "cat"], cert: ["certs", "[data-cert]", "cert"] }[p[0]];
      if (map) {
        toggleIn(state.filters[map[0]], p[1]);
        $$(map[1]).forEach(function (c) { c.classList.toggle("on", state.filters[map[0]].indexOf(c.dataset[map[2]]) >= 0); });
      }
    }
    applyAll();
  }

  function resetAll() {
    state.filters = { q: "", prov: "", city: "", firms: [], cats: [], certs: [], time: "all", sort: "new" };
    $("#kw").value = ""; $("#clearKw").hidden = true;
    $("#province").value = ""; $("#sort").value = "new";
    refreshCityOptions(); $("#city").value = "";
    $$(".chip.on").forEach(function (c) { c.classList.remove("on"); });
    $$("#timeRow [data-time='all']").forEach(function (c) { c.classList.add("on"); });
    applyAll();
  }

  function openSheet(id) {
    var j = state.jobs.filter(function (x) { return x.id === id || x.slug === id; })[0];
    if (!j) return;
    $("#sheetFirm").textContent = j.firm + (j.branch ? " · " + j.branch : "");
    $("#sheetTitle").textContent = j.title;
    var meta = [];
    if (j.city) meta.push('<span class="tag city">' + esc(j.city) + (j.province && j.province !== j.city ? " · " + esc(j.province) : "") + "</span>");
    if (j.category) meta.push('<span class="tag cat">' + esc(j.category) + "</span>");
    (j.certs || []).filter(function (c) { return c !== "不限"; }).forEach(function (c) { meta.push('<span class="tag cert">' + esc(c) + "</span>"); });
    if (j.published_at) meta.push('<span class="tag">' + esc(relDate(j.published_at)) + "</span>");
    if (j.headcount) meta.push('<span class="tag">招 ' + esc(j.headcount) + " 人</span>");
    $("#sheetMeta").innerHTML = meta.join("");
    var body = "";
    if (j.responsibilities) body += "<h3>岗位职责</h3><p>" + esc(j.responsibilities) + "</p>";
    if (j.requirements) body += "<h3>任职要求</h3><p>" + esc(j.requirements) + "</p>";
    if (!body && j.summary) body = "<h3>岗位摘要</h3><p>" + esc(j.summary) + "</p>";
    body += '<p class="src">来源：' + esc(j.source_name || (j.firm + "官方招聘渠道")) + " · 采集时间 " + esc(j.last_seen || "") +
      "<br>投递前请以官方页面最新信息为准，本站不收集简历。</p>";
    $("#sheetBody").innerHTML = body;
    $("#sheetApply").href = j.url || "#";
    $("#sheetMask").dataset.id = j.id;
    $("#sheetMask").hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closeSheet() {
    $("#sheetMask").hidden = true;
    document.body.style.overflow = "";
    var p = new URLSearchParams(location.search);
    if (p.get("job")) {
      p.delete("job");
      history.replaceState(null, "", location.pathname + (p.toString() ? "?" + p : ""));
    }
  }

  function sharePage() {
    var url = location.href;
    if (navigator.share) {
      navigator.share({ title: "确实在审 · 财会行业招聘信息查询", text: "财会行业招聘信息查询结果分享", url: url }).catch(function () {});
      return;
    }
    copyText(url).then(function (ok) { toast(ok ? "筛选结果的链接已复制，粘贴到微信即可分享" : "复制失败，请手动复制地址栏"); });
  }
  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(function () { return true; }).catch(function () { return legacyCopy(text); });
    }
    return Promise.resolve(legacyCopy(text));
  }
  function legacyCopy(text) {
    try {
      var ta = document.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      var ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch (e) { return false; }
  }
  var toastTimer = null;
  function toast(msg) {
    var el = $("#toast");
    el.textContent = msg; el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.hidden = true; }, 2600);
  }

  loadData().then(boot).catch(function (err) {
    $("#resultCount").textContent = "岗位数据读取失败";
    $("#empty").hidden = false;
    $("#empty").querySelector("p").textContent = "数据文件未找到或格式错误";
    $("#empty").querySelector(".empty-sub").textContent = "请通过本地服务器打开（python3 scripts/serve.py）。" + (err && err.message ? "（" + err.message + "）" : "");
  });
})();
