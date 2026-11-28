/* 确实在审 — 实习招聘前端逻辑（无依赖，移动优先） */
(function () {
  "use strict";

  var state = {
    data: null,
    jobs: [],
    filters: { q: "", prov: "", city: "", firms: [], types: [], edu: [], start: [], salary: [], time: "all", sort: "new" },
    page: 1, pageSize: 30, filtered: []
  };

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  var UNKNOWN = "未披露";
  var PROVINCE_ORDER = ["北京","上海","天津","重庆","广东","江苏","浙江","山东","福建","四川","湖北","湖南","河南","河北","安徽","江西","陕西","山西","辽宁","吉林","黑龙江","云南","贵州","广西","海南","内蒙古","甘肃","青海","宁夏","新疆","西藏","香港","澳门","台湾"];
  var HOT_CITIES = ["北京","上海","深圳","广州","杭州","南京","苏州","成都","武汉","西安","重庆","天津","长沙","合肥","济南","无锡","厦门","郑州"];
  var TYPE_ORDER = ["年报审计实习","寒暑假实习","日常审计实习","税务实习","咨询实习","资产评估实习","其他实习"];

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
  function deadlineHint(j) {
    if (!j.deadline || j.deadline === UNKNOWN) return "";
    var d = parseDate(j.deadline);
    if (!d) return "";
    var diff = daysBetween(new Date(), d);
    if (diff >= 0 && diff <= 7) return "即将截止";
    return "";
  }
  function eduBucket(edu) {
    if (!edu || edu === UNKNOWN) return UNKNOWN;
    if (edu.indexOf("博士") >= 0) return "博士";
    if (edu.indexOf("硕士") >= 0 || edu.indexOf("研究生") >= 0) return "硕士及以上";
    if (edu.indexOf("本科") >= 0) return "本科";
    if (edu.indexOf("大专") >= 0 || edu.indexOf("专科") >= 0) return "大专";
    if (edu.indexOf("学历不限") >= 0) return "学历不限";
    return UNKNOWN;
  }
  function startBucket(s) {
    if (!s || s === UNKNOWN) return UNKNOWN;
    if (s.indexOf("尽快") >= 0 || s.indexOf("随时") >= 0) return "尽快到岗";
    return "已注明时间";
  }

  function loadData() {
    return fetch("data/intern/jobs.json", { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).catch(function () {
      return new Promise(function (resolve, reject) {
        var s = document.createElement("script");
        s.src = "assets/js/data-fallback-intern.js";
        s.onload = function () { window.__INTERN_JOBS_DATA ? resolve(window.__INTERN_JOBS_DATA) : reject(new Error("fallback empty")); };
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
    var provs = {}, cities = {}, firms = {}, types = {}, edus = {}, starts = {}, sals = {};
    state.jobs.forEach(function (j) {
      if (j.province) provs[j.province] = (provs[j.province] || 0) + 1;
      if (j.city) cities[j.city] = (cities[j.city] || 0) + 1;
      if (j.firm) firms[j.firm] = (firms[j.firm] || 0) + 1;
      if (j.intern_type) types[j.intern_type] = (types[j.intern_type] || 0) + 1;
      var eb = eduBucket(j.education); if (eb) edus[eb] = (edus[eb] || 0) + 1;
      var sb = startBucket(j.intern_start); if (sb) starts[sb] = (starts[sb] || 0) + 1;
      var sl = (j.salary && j.salary !== UNKNOWN) ? "有薪酬" : UNKNOWN; sals[sl] = (sals[sl] || 0) + 1;
    });

    $("#province").innerHTML = '<option value="">全部省份</option>' + Object.keys(provs).sort(function (a, b) {
      var ia = PROVINCE_ORDER.indexOf(a), ib = PROVINCE_ORDER.indexOf(b);
      if (ia < 0) ia = 99; if (ib < 0) ib = 99;
      return ia - ib || a.localeCompare(b, "zh");
    }).map(function (p) { return '<option value="' + esc(p) + '">' + esc(p) + "（" + provs[p] + "）</option>"; }).join("");

    $("#firmChips").innerHTML = Object.keys(firms).sort(function (a, b) { return firms[b] - firms[a]; }).map(function (f) {
      return '<button type="button" class="chip sm" data-firm="' + esc(f) + '">' + esc(f) + '<span style="opacity:.55;margin-left:4px">' + firms[f] + "</span></button>";
    }).join("");

    $("#typeChips").innerHTML = Object.keys(types).sort(function (a, b) { return TYPE_ORDER.indexOf(a) - TYPE_ORDER.indexOf(b); }).map(function (t) {
      return '<button type="button" class="chip sm" data-type="' + esc(t) + '">' + esc(t) + '<span style="opacity:.55;margin-left:4px">' + types[t] + "</span></button>";
    }).join("");

    $("#eduChips").innerHTML = Object.keys(edus).sort(function (a, b) { return edus[b] - edus[a]; }).map(function (e) {
      return '<button type="button" class="chip sm" data-edu="' + esc(e) + '">' + esc(e) + '<span style="opacity:.55;margin-left:4px">' + edus[e] + "</span></button>";
    }).join("");

    $("#startChips").innerHTML = Object.keys(starts).sort(function (a, b) { return starts[b] - starts[a]; }).map(function (s) {
      return '<button type="button" class="chip sm" data-start="' + esc(s) + '">' + esc(s) + '<span style="opacity:.55;margin-left:4px">' + starts[s] + "</span></button>";
    }).join("");

    $("#salaryChips").innerHTML = Object.keys(sals).sort(function (a, b) { return sals[b] - sals[a]; }).map(function (s) {
      return '<button type="button" class="chip sm" data-salary="' + esc(s) + '">' + esc(s) + '<span style="opacity:.55;margin-left:4px">' + sals[s] + "</span></button>";
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
      if (f.types.length && f.types.indexOf(j.intern_type) < 0) return false;
      if (f.edu.length && f.edu.indexOf(eduBucket(j.education)) < 0) return false;
      if (f.start.length && f.start.indexOf(startBucket(j.intern_start)) < 0) return false;
      if (f.salary.length) {
        var sl = (j.salary && j.salary !== UNKNOWN) ? "有薪酬" : UNKNOWN;
        if (f.salary.indexOf(sl) < 0) return false;
      }
      if (!matchTime(j)) return false;
      if (terms.length) {
        var hay = [j.title, j.firm, j.city, j.province, j.intern_type, j.education, j.salary, j.housing, j.summary, j.requirements].join(" ").toLowerCase();
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
      if (s === "deadline") return cmpDeadline(a, b) || cmpDate(a, b);
      return cmpDate(a, b);
    });
  }
  function cmpDate(a, b) {
    return (parseDate(b.published_at) || new Date(0)) - (parseDate(a.published_at) || new Date(0));
  }
  function cmpDeadline(a, b) {
    var da = parseDate(a.deadline), db = parseDate(b.deadline);
    if (da && db) return da - db;
    if (da) return -1;
    if (db) return 1;
    return 0;
  }

  function renderList() {
    var list = $("#list"), total = state.filtered.length, shown = Math.min(total, state.page * state.pageSize);
    $("#resultCount").innerHTML = total ? "共 <b>" + total + "</b> 个在招实习岗位" + (total > shown ? "，已显示 " + shown + " 个" : "") : "";
    if (!total) {
      list.innerHTML = ""; $("#empty").hidden = false; $("#loadMore").hidden = true;
      $("#resultCount").textContent = "没有匹配的实习岗位";
      return;
    }
    $("#empty").hidden = true;
    list.innerHTML = state.filtered.slice(0, shown).map(cardHTML).join("");
    $("#loadMore").hidden = shown >= total;
    $("#loadMore").textContent = "加载更多岗位（还有 " + (total - shown) + " 个）";
  }

  function cardHTML(j) {
    var isNew = daysBetween(parseDate(j.first_seen), new Date()) <= 2;
    var dd = deadlineHint(j);
    var tags = [];
    if (j.city) tags.push('<span class="tag city">' + esc(j.city) + "</span>");
    if (j.intern_type) tags.push('<span class="tag cat">' + esc(j.intern_type) + "</span>");
    if (j.education && j.education !== UNKNOWN) tags.push('<span class="tag edu">' + esc(j.education) + "</span>");
    if (j.salary && j.salary !== UNKNOWN) tags.push('<span class="tag pay">' + esc(j.salary) + "</span>");
    return '<article class="job-card' + (j.intern_type === "年报审计实习" ? " hot" : "") + '" data-id="' + esc(j.id) + '">' +
      '<div class="job-top"><div style="min-width:0">' +
        '<h2 class="job-title">' + esc(j.title) +
          (isNew ? '<span class="new-dot">NEW</span>' : "") +
          (dd ? '<span class="deadline-dot">' + esc(dd) + "</span>" : "") +
        "</h2>" +
        '<div class="job-firm"><span class="firm-logo">' + esc((j.firm || "?").slice(0, 1)) + "</span>" + esc(j.firm) + (j.branch ? " · " + esc(j.branch) : "") + "</div>" +
      "</div>" +
      '<span class="job-date">' + esc(relDate(j.published_at)) + "</span></div>" +
      '<div class="job-meta">' + tags.join("") + "</div>" +
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
    f.types.forEach(function (x) { parts.push(pill(x, "type|" + x)); });
    f.edu.forEach(function (x) { parts.push(pill(x, "edu|" + x)); });
    f.start.forEach(function (x) { parts.push(pill(x, "start|" + x)); });
    f.salary.forEach(function (x) { parts.push(pill(x, "salary|" + x)); });
    if (f.time !== "all") parts.push(pill({ today: "今日新增", "7": "近 7 天", "30": "近 30 天" }[f.time], "time"));
    var box = $("#activeFilters");
    box.innerHTML = parts.join("");
    box.hidden = parts.length === 0;
  }
  function pill(text, key) { return '<span class="pill">' + esc(text) + '<button type="button" data-rm="' + esc(key) + '" aria-label="移除">×</button></span>'; }

  function updateFilterBadge() {
    var f = state.filters;
    var n = (f.prov ? 1 : 0) + (f.city ? 1 : 0) + f.firms.length + f.types.length + f.edu.length + f.start.length + f.salary.length + (f.time !== "all" ? 1 : 0);
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
    if (f.types.length) p.set("types", f.types.join(","));
    if (f.edu.length) p.set("edu", f.edu.join(","));
    if (f.start.length) p.set("start", f.start.join(","));
    if (f.salary.length) p.set("salary", f.salary.join(","));
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
    f.types = (p.get("types") || "").split(",").filter(Boolean);
    f.edu = (p.get("edu") || "").split(",").filter(Boolean);
    f.start = (p.get("start") || "").split(",").filter(Boolean);
    f.salary = (p.get("salary") || "").split(",").filter(Boolean);
    f.time = p.get("time") || "all";
    f.sort = p.get("sort") || "new";
    $("#kw").value = f.q;
    $("#province").value = f.prov;
    refreshCityOptions();
    $("#city").value = f.city;
    $("#sort").value = f.sort;
    $$("[data-firm]").forEach(function (c) { c.classList.toggle("on", f.firms.indexOf(c.dataset.firm) >= 0); });
    $$("[data-type]").forEach(function (c) { c.classList.toggle("on", f.types.indexOf(c.dataset.type) >= 0); });
    $$("[data-edu]").forEach(function (c) { c.classList.toggle("on", f.edu.indexOf(c.dataset.edu) >= 0); });
    $$("[data-start]").forEach(function (c) { c.classList.toggle("on", f.start.indexOf(c.dataset.start) >= 0); });
    $$("[data-salary]").forEach(function (c) { c.classList.toggle("on", f.salary.indexOf(c.dataset.salary) >= 0); });
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
      var ty = e.target.closest("[data-type]");
      if (ty) { toggleIn(state.filters.types, ty.dataset.type); ty.classList.toggle("on"); applyAll(); return; }
      var ed = e.target.closest("[data-edu]");
      if (ed) { toggleIn(state.filters.edu, ed.dataset.edu); ed.classList.toggle("on"); applyAll(); return; }
      var st = e.target.closest("[data-start]");
      if (st) { toggleIn(state.filters.start, st.dataset.start); st.classList.toggle("on"); applyAll(); return; }
      var sa = e.target.closest("[data-salary]");
      if (sa) { toggleIn(state.filters.salary, sa.dataset.salary); sa.classList.toggle("on"); applyAll(); return; }
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
      var p = key.split("|"), map = { firm: ["firms", "[data-firm]", "firm"], type: ["types", "[data-type]", "type"], edu: ["edu", "[data-edu]", "edu"], start: ["start", "[data-start]", "start"], salary: ["salary", "[data-salary]", "salary"] }[p[0]];
      if (map) {
        toggleIn(state.filters[map[0]], p[1]);
        $$(map[1]).forEach(function (c) { c.classList.toggle("on", state.filters[map[0]].indexOf(c.dataset[map[2]]) >= 0); });
      }
    }
    applyAll();
  }

  function resetAll() {
    state.filters = { q: "", prov: "", city: "", firms: [], types: [], edu: [], start: [], salary: [], time: "all", sort: "new" };
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
    if (j.intern_type) meta.push('<span class="tag cat">' + esc(j.intern_type) + "</span>");
    if (j.education && j.education !== UNKNOWN) meta.push('<span class="tag edu">' + esc(j.education) + "</span>");
    if (j.published_at) meta.push('<span class="tag">' + esc(relDate(j.published_at)) + "</span>");
    $("#sheetMeta").innerHTML = meta.join("");
    var body = '<div class="sheet-facts">';
    body += fact("实习开始", j.intern_start);
    body += fact("实习时长", j.duration);
    body += fact("每周出勤", j.weekly_attendance);
    body += fact("薪酬补贴", j.salary);
    body += fact("是否住宿", j.housing);
    body += fact("招聘截止", j.deadline);
    body += fact("招聘人数", j.headcount);
    body += fact("投递邮箱", j.apply_email || "未披露");
    body += "</div>";
    if (j.responsibilities) body += "<h3>岗位职责</h3><p>" + esc(j.responsibilities) + "</p>";
    if (j.requirements) body += "<h3>任职要求</h3><p>" + esc(j.requirements) + "</p>";
    if (!j.responsibilities && !j.requirements && j.summary) body = "<h3>岗位摘要</h3><p>" + esc(j.summary) + "</p>" + body;
    body += '<p class="src">来源：' + esc(j.source_name || (j.firm + "官方招聘渠道")) + " · 核验时间 " + esc((j.verified_at || j.last_seen || "").slice(0, 10)) +
      "<br>投递前请以官方页面最新信息为准，本站不收集简历、不提供收费内推。</p>";
    $("#sheetBody").innerHTML = body;
    $("#sheetApply").href = j.url || "#";
    $("#sheetMask").dataset.id = j.id;
    $("#sheetMask").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function fact(k, v) {
    var val = v && v !== UNKNOWN ? esc(v) : '<span class="muted">未披露</span>';
    return '<div class="fact"><span class="fact-k">' + esc(k) + "</span><span class='fact-v'>" + val + "</span></div>";
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
      navigator.share({ title: "确实在审 · 实习招聘", text: "财会行业实习岗位查询", url: url }).catch(function () {});
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
    $("#resultCount").textContent = "实习岗位数据读取失败";
    $("#empty").hidden = false;
    $("#empty").querySelector("p").textContent = "数据文件未找到或格式错误";
    $("#empty").querySelector(".empty-sub").textContent = "请通过本地服务器打开（python3 scripts/serve.py）。" + (err && err.message ? "（" + err.message + "）" : "");
  });
})();
