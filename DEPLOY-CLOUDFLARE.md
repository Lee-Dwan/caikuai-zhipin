> ⚠️ 实测记录：在中国大陆家庭宽带直连测试中，`*.pages.dev` 出现 TLS 握手 13～15 秒、传输被重置，20 秒仅收到 8～11KB，判定为不可用。本项目最终采用 **GitHub Pages** 上线（见 `reports/ONLINE-REPORT.md`）。本文仅作为备选方案保留。

# Cloudflare Pages 免费部署说明

全程免费：GitHub 公共仓库（代码 + Actions 2000 分钟/月）+ Cloudflare Pages 免费版（静态站点无限带宽、每月 500 次构建）。无需服务器、域名、数据库。

## 一、把代码推到 GitHub

```bash
cd caikuai-zhipin
git init
git add .
git commit -m "feat: 财会职聘 V1.0 上线"
git branch -M main
git remote add origin https://github.com/<你的用户名>/caikuai-zhipin.git
git push -u origin main
```

仓库建议设为 Public（Pages 免费版对公共仓库无额外限制；私有仓库也可用，但团队协作会占用席位）。

## 二、开启 Actions 写权限（关键）

仓库 → Settings → Actions → General → Workflow permissions → 选 **Read and write permissions** → Save。

否则每天采集完成后 `git push` 会失败（报 403），数据虽然采到了但不会提交、站点也不会更新。

然后在 Actions 页面手动点一次 **Run workflow**，确认 `每日采集招聘数据` 跑通、仓库里 `data/jobs.json` 有更新。

## 三、在 Cloudflare Pages 创建项目

1. 登录 https://dash.cloudflare.com/ → 左侧 **Workers & Pages** → **Create** → **Pages** → **Connect to Git**。
2. 授权 GitHub，选择 `caikuai-zhipin` 仓库，分支 `main`。
3. 构建配置：
   - Framework preset：**None**
   - Build command：**留空**（纯静态，无构建）
   - Build output directory：**`/`**（若界面要求相对路径，填 `.`）
4. 点 **Save and Deploy**。约 1 分钟后得到域名：`https://caikuai-zhipin.pages.dev`。

## 四、自动更新的两种方式

**方式 A（推荐，零配置）**：Pages 已连接 Git 仓库，Actions 每天提交数据后 Cloudflare 会自动重新部署，对外链接不变。

**方式 B（可选，Deploy Hook）**：Pages 项目 → Settings → Builds & deployments → Deploy hooks → 新建 hook，复制 URL，在 GitHub 仓库 Settings → Secrets and variables → Actions 新建 secret `CF_DEPLOY_HOOK`，并在 `collect.yml` 的“提交数据更新”步骤后追加：

```yaml
      - name: 触发 Cloudflare Pages 重新部署
        if: env.CF_DEPLOY_HOOK != ''
        env:
          CF_DEPLOY_HOOK: ${{ secrets.CF_DEPLOY_HOOK }}
        run: curl -fsS -X POST "$CF_DEPLOY_HOOK"
```

方式 A 已能满足“每天 8 点更新、链接不变”的要求，方式 B 仅在需要精确控制部署时机时使用。

## 五、部署后自检清单

- [ ] 打开 `https://<项目>.pages.dev`，首屏统计有真实数字（不是 0、不是占位）
- [ ] `https://<项目>.pages.dev/data/jobs.json` 可直接访问且是 JSON
- [ ] 搜索“审计”、切换省份、勾选 CPA、点“今日新增/近 7 天”均有结果
- [ ] 任取一条岗位点“官方投递”，能跳到事务所官方页面
- [ ] 手机上打开，筛选面板可展开、卡片不横向溢出
- [ ] Actions 次日 08:00 自动运行，`data/jobs.json` 的 `meta.generated_at` 更新

## 六、自定义域名（可选，不花钱也能上线）

`*.pages.dev` 域名已可公开访问、可用于分享。若要绑定自有域名：Pages → Custom domains → Set up a domain，按提示在 DNS 添加 CNAME；域名本身需另行购买，本项目不强制。

## 七、常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| Actions 报 `remote: Permission denied` | 未开写权限 | 见第二节 |
| 页面统计全是 0 | `data/jobs.json` 未提交或未部署 | 本地跑 `collect.py`，确认文件存在后重新 push |
| 打开页面空白、控制台 404 | 访问路径不是站点根目录 | 用 `pages.dev` 域名访问，不要用 file:// |
| 构建失败 `Output directory "..." not found` | 输出目录填错 | 改为 `/` 或 `.` |
| 数据是旧的 | Cloudflare 缓存 | `_headers` 已对 `/data/*` 设 5 分钟缓存，等 5 分钟或 Purge Cache |
