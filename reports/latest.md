# 采集报告

- 采集时间：2026-11-28T08:50:57+08:00（北京时间）
- 成功率：10/11（90.9%）
- 在招岗位：1223 条；覆盖事务所：11 家；今日新增：2

## 各数据源

| 事务所 | 状态 | 条数 | 耗时(s) | 说明 |
| --- | --- | --- | --- | --- |
| 立信 | 成功 | 178 | 2.6 | - |
| 大华 | 成功 | 66 | 1.8 | - |
| 大信 | 成功 | 52 | 1.6 | - |
| 安永 | 成功 | 81 | 84.3 | - |
| 致同 | 成功 | 88 | 1.7 | - |
| 容诚 | 失败 | 0 | 160.5 | RuntimeError: HTTPSConnectionPool(host='careers.rccpa.com.cn', port=443): Max retries exceeded with url: /eRecruit/recruit/position/getIndexPositions?type=2&titleSite= (Caused by ConnectTimeoutError(<HTTPSConnection(host='careers.rccpa.com.cn', port=443) at 0x76f0fefbf9b0>, 'Connection to careers.rccpa.com.cn timed out. (connect timeout=25)')) |
| 信永中和 | 成功 | 219 | 106.6 | - |
| 天健 | 成功 | 94 | 1.6 | - |
| 天职国际 | 成功 | 320 | 5.6 | - |
| 中汇 | 成功 | 77 | 1.6 | - |
| 中审众环 | 成功 | 22 | 2.1 | - |

## 未纳入自动采集

- **天衡**：官网 join-us 栏目仅有校园招聘信息，暂无公开社招岗位
- **德勤**：官方招聘门户为 SuccessFactors/wecruit，需登录交互，未开放公开岗位列表接口
- **普华永道**：官网(Workday)存在频率限制，CX 接口持续返回 429，无法稳定自动采集；仅保留官网入口
- **毕马威**：官网招聘页无岗位列表与公开接口（job-search 页面 404）
- **苏亚金诚**：官网仅有招聘简介与邮箱投递方式，无结构化岗位列表

## 数据口径

- 仅收录社会招聘，校招/实习岗位在采集阶段即被排除；
- 岗位连续 2 次采集成功且官网未再出现才判定下架；采集失败时保留历史数据并标记异常；
- 投递链接均指向事务所官方页面。
