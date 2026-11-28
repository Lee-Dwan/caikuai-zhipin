# 确实在审 · 财会行业招聘信息查询

只收录**社会招聘**（不含校园招聘、实习）的会计师事务所岗位聚合站；另有独立的**实习招聘**模块（`intern.html`）。纯静态站点，零服务器、零数据库、零付费 API，也是「确实在审」个人品牌的长期工具平台。

- 前端：原生 HTML / CSS / JavaScript（无框架、无构建步骤）
- 数据：`data/jobs.json`（静态 JSON）+ `assets/js/data-fallback.js`（本地双击预览兜底）
- 采集：Python 脚本，逐个事务所独立模块
- 更新：GitHub Actions 每天北京时间 08:00 自动采集并提交数据
- 部署：GitHub Pages（连接 GitHub 仓库，push 即自动发布；实测国内直连 0.5 秒级）

## 当前数据（2026-11-27 首次上线）

- 在招社招岗位 **1,220** 条，覆盖 **11** 家事务所，采集成功率 **11/11（100%）**
- 岗位类别：审计 559 / 咨询 260 / 税务 148 / 其他 107 / 评估 74 / 工程造价 72
- 证书要求：不限 608 / CPA 455 / 其他证书 152 / ACCA 100 / 税务师 87 / 中级会计师 19
- 省份 Top：北京 266 / 广东 161 / 上海 108 / 浙江 86 / 江苏 57 / 湖北 50
- 缓存建立后单轮采集约 45 秒；首次全量约 11 分钟（安永 Taleo 详情页较慢）

## 功能

- 关键词搜索（岗位名 / 事务所 / 城市 / 证书 / 要求正文，多词空格分隔）
- 省份 → 城市联动筛选、事务所多选、岗位类别（审计 / 税务 / 咨询 / 评估 / 工程造价 / 其他）、证书要求（CPA / 税务师 / 中级会计师 / ACCA / 其他）
- 今日新增、近 7 天、近 30 天；按发布时间 / 事务所 / 城市排序
- 岗位详情抽屉：职责、要求、人数、发布时间、官方投递链接（新窗口打开）
- 筛选结果链接分享（URL 参数完整还原筛选条件）、单岗位分享
- 首页真实统计：在招岗位数、覆盖事务所数、今日新增、最近更新时间
- 公众号 / 小红书 / 抖音二维码展示位
- 移动端优先，桌面端自适应
- 不设登录注册，不收集简历与任何个人信息
- **实习招聘模块**（`intern.html`）：按城市 / 事务所 / 实习类型 / 学历 / 实习时间 / 薪酬 / 发布时间筛选，突出年审实习、即将截止、近期新增；真实实习数据，缺失字段标注「未披露」

## 目录结构

```
.
├── index.html                  # 社会招聘单页站点
├── intern.html                 # 实习招聘单页站点
├── assets/
│   ├── css/style.css           # 全部样式（移动优先）
│   ├── js/app.js               # 社会招聘筛选 / 搜索 / 详情 / 分享逻辑
│   ├── js/app_intern.js        # 实习招聘筛选 / 搜索 / 详情 / 分享逻辑
│   └── js/data-fallback*.js    # 由采集脚本生成，离线预览用
├── data/
│   ├── jobs.json               # 社会招聘数据（含 meta）
│   ├── meta.json               # 社会招聘元数据
│   ├── firms.json              # 社会招聘数据源清单
│   ├── state.json              # 社会招聘采集状态
│   ├── collect-report.json     # 社会招聘采集报告
│   └── intern/                 # 实习招聘数据（jobs/meta/firms/state/collect-report/discovery-*）
├── reports/latest.md           # 最近一次社会招聘采集报告
├── reports/INTERN-MAINTENANCE.md
├── scripts/
│   ├── collect.py              # 社会招聘采集入口
│   ├── collect_intern.py       # 实习采集入口
│   ├── normalize.py            # 城市→省份、类别、证书、摘要、ID
│   ├── store.py                # 社会招聘去重 / 下架 / 输出
│   ├── intern_collectors.py    # 实习采集器集合
│   ├── intern_store.py         # 实习去重 / 下架 / 输出
│   ├── discover.py             # 社会招聘来源发现
│   ├── discover_intern.py      # 实习来源发现
│   ├── serve.py                # 本地预览服务器
│   └── collectors/             # 社会招聘采集器
├── .github/workflows/collect.yml
├── _headers                    # Cloudflare Pages 响应头
├── requirements.txt
├── README.md
├── DEPLOY-CLOUDFLARE.md
└── MAINTAIN.md
```

## 线上地址

- 网站：https://Lee-Dwan.github.io/caikuai-zhipin/
- 仓库：https://github.com/Lee-Dwan/caikuai-zhipin
- 上线与实测记录：`reports/ONLINE-REPORT.md`

## 本地运行

```bash
# 1. 采集（需要联网）
pip install -r requirements.txt
python3 scripts/collect.py

# 2. 预览（推荐，数据走 fetch）
python3 scripts/serve.py --port 8080
# 打开 http://127.0.0.1:8080/

# 也可以直接双击 index.html（会回退读取 assets/js/data-fallback.js）
```

只跑某几家：`python3 scripts/collect.py --firms tianjian,ey`

## 数据口径

- **只收社招**：北森门户按 `Category=社会招聘` 过滤；天健按 `jobPersonProperty=1`；容诚用 `type=2`；标题含“实习”的一律排除。
- **不编造**：采集失败的机构保留历史数据并标记异常，绝不用推测内容填充；无公开岗位列表的机构如实标注原因（见 `data/firms.json`）。
- **下架判定**：某岗位连续 **2 次**“该事务所采集成功但榜单中不再出现”才标记为 closed；采集失败那一轮不做任何下架判定。
- **新增判定**：以 `first_seen` 日期为准，首次建立基线当天不计“今日新增”，此后按自然日统计。
- **投递链接**：一律指向事务所官方页面。容诚的岗位详情是页面内弹层，没有独立详情 URL，链接指向其官方招聘门户首页，并在详情中注明。
- **字段完整性**：城市、省份、发布时间可能因官方页面未提供而留空，前端会以“时间待核”或省略标签的方式如实呈现，不做补造。

## 数据源覆盖（首批 16 家）

| 事务所 | 采集方式 | 状态 |
| --- | --- | --- |
| 天健 | 官方招聘系统公开接口 | 自动采集 |
| 立信、天职国际、致同、中汇、中审众环、大华、大信 | 北森 iTalent 门户公开接口 | 自动采集 |
| 信永中和 | 官方招聘系统公开接口（详情走本地缓存 + 限速） | 自动采集 |
| 容诚 | 官方门户公开接口（无独立详情页） | 自动采集 |
| 安永 | 官方 Taleo 招聘站列表 + 详情微数据 | 自动采集 |
| 普华永道 | 官网 Workday 接口持续 429 限流 | 不自动采集，仅官网入口 |
| 德勤 | SuccessFactors 门户，无公开岗位列表接口 | 不自动采集，仅官网入口 |
| 毕马威 | 官网无岗位列表、无公开接口 | 不自动采集，仅官网入口 |
| 天衡 | 官网仅校园招聘信息 | 暂无社招 |
| 苏亚金诚 | 官网仅招聘简介与邮箱投递 | 无结构化岗位 |

具体条数与耗时见 `reports/latest.md`。

## 免责声明

本站为个人自媒体信息聚合，岗位信息版权归各事务所所有，均来自其官方公开招聘页面；信息可能滞后，投递前请以官方页面为准。本站不收集、不存储求职者任何个人信息。
