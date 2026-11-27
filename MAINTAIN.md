# 维护手册

## 一、新增一家事务所（三步）

以“某某会计师事务所”官网为例，先确认它有**可公开访问的岗位列表**（不需要登录、没有验证码、没有强风控）。

1. **新建采集模块** `scripts/collectors/<firm_id>.py`

```python
from .base import Collector, RawJob, register

@register
class XinFirm(Collector):
    firm_id = "xinfirm"          # 唯一英文 id，勿与已有重复
    firm_name = "某某"            # 页面显示名称
    source_name = "某某官方招聘系统（example.com）"
    homepage = "https://example.com/jobs"

    def fetch(self) -> list[RawJob]:
        # 在这里请求官方接口/页面，只保留社会招聘，返回 RawJob 列表
        return [RawJob(title="审计经理", url="https://example.com/job/1",
                       city="南京", published_at="2026-11-20",
                       responsibilities="...", requirements="...")]
```

`RawJob` 可用字段：`title, url`（必填）、`city, province, category, published_at, branch, headcount, responsibilities, requirements, summary`。

2. **在 `scripts/collectors/__init__.py` 的 `MODULES` 里加模块名**，否则不会被加载。

3. **单独测试，再全量**

```bash
python3 scripts/collect.py --firms xinfirm --no-merge   # 只看抓取结果，不写数据
python3 scripts/collect.py --firms xinfirm              # 正式入库
```

确认条数合理、城市能映射到省份（不能映射的会被留空，见 `normalize.py` 的 `CITY_TO_PROVINCE`）、投递链接能打开。

**没有公开列表的机构不要硬写采集器**，把它加到 `scripts/collect.py` 的 `NO_PUBLIC` 字典，写清原因和官网入口，页面会如实显示“暂未纳入自动采集”。

## 二、删除或暂停一家事务所

- 暂停：在采集器里设 `enabled = False`，或在 `collect.py` 的 `NO_PUBLIC` 里补一条说明。
- 彻底删除：删掉模块文件与 `MODULES` 中的引用。历史岗位会在后续两轮采集后自动转为 closed（若该所已不再采集，历史数据会保留，直到手工清理 `data/state.json`）。

## 三、修改品牌

| 要改的地方 | 位置 |
| --- | --- |
| 站点名称、标题、SEO 描述 | `index.html` 的 `<title>`、`<meta name="description">`、`og:*`、header 的 logo 文字 |
| 主色 | `assets/css/style.css` 顶部 `:root` 中的 `--ink`、`--accent`、`--gold` |
| 页脚署名 / 免责声明 | `index.html` footer |
| 公众号 / 小红书 / 抖音二维码 | `index.html` 的 `follow` 区块，把占位块换成 `<img src="assets/img/xxx.png">` |
| 分享文案 | `assets/js/app.js` 里的 `navigator.share` / `toast` 文案 |

改完直接 push，Pages 自动重新部署。

## 四、数据规则（改动前务必理解）

- `data/state.json` 是**唯一的事实来源**：记录每个岗位的 `first_seen / last_seen / miss_count / status`。不要手工编辑，尤其不要批量删 `jobs`。
- `data/jobs.json` 是**派生文件**，可以随时由 `collect.py` 重新生成；不要手工改它，否则下一轮采集会被覆盖。
- 下架需要连续 2 轮“采集成功但岗位消失”，阈值在 `store.py` 的 `MISS_THRESHOLD`。调低会让偶发漏抓直接下架，不建议。
- 已下架岗位保留 120 天（`CLOSED_KEEP_DAYS`）后自动清理。
- 首次运行会建立基线，当天“今日新增”显示 0；从第二天起按自然日统计新增。

## 五、常见故障

| 现象 | 排查 |
| --- | --- |
| 某所突然 0 条 | 先手动跑 `--firms <id>` 看错误；多为官网接口变更或临时风控，页面会标“采集异常”并保留历史岗位 |
| 信永中和报连接重置 | 站点对高频详情请求敏感。已做本地缓存 + 约 1 秒间隔 + 每轮最多 70 条新详情，若仍失败，等下一轮或把 `DETAIL_BUDGET` 调低 |
| 安永采集很慢（约 4~5 分钟） | Taleo 详情页响应慢，属正常；已限制最多 90 条详情，只影响 Actions 时长，不影响数据 |
| 城市筛选项里出现奇怪值 | 在 `normalize.py` 的 `CITY_TO_PROVINCE` 补映射，或在 `NO_CITY` 里加排除值 |
| 页面统计与 JSON 不一致 | 浏览器缓存，强刷或等 5 分钟（`/data/*` 缓存 300 秒） |
| Actions 跑成功但站点没变 | 检查 Actions 是否真的 `git push` 成功（写权限），以及 Pages 是否触发了新部署 |

## 六、合规底线

- 只抓官方公开页面，不绕过登录、验证码、付费墙；
- 不复制其他招聘站的品牌、代码或数据库；
- 采集失败的机构不得编造岗位，宁缺毋滥；
- 不在站内收集求职者简历或个人信息。
