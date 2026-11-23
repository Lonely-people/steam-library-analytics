# Steam 个人游戏库与游玩成本分析系统

课程实验三（数据库应用实践）v1.0 基础版。本地 Ubuntu 上运行 Flask，
数据存储在华为云 ECS 上的 openGauss。

## 1. 运行环境

| 组件 | 版本 / 说明 |
|---|---|
| 操作系统 | Ubuntu 22.04 LTS |
| Python | 3.11，由 `uv` 独立管理（不改系统 Python） |
| Web 框架 | Flask 3.x + Jinja2 |
| 数据库驱动 | `psycopg2-binary`（已实测与 openGauss 7.0.0-RC3 兼容） |
| 数据库 | openGauss 7.0.0-RC3（华为云 ECS，Docker 容器） |
| 前端 | Bootstrap 5.3.3 + 原生 JS + ECharts 5.6.0（均为本地静态资源，无 CDN） |

## 2. 首次运行

```bash
# 依赖与环境
uv sync

# 配置（不要把真实密码提交进 Git）
cp .env.example .env
# 编辑 .env：DB_PASSWORD、以及 Steam 同步需要的 STEAM_API_KEY / STEAM_ID64
```

### 2.1 建立数据库连接

数据库在 ECS 上通过 SSH 隧道访问：

```bash
# 在本地 Ubuntu 终端执行，保持窗口打开
ssh -N -L 15432:127.0.0.1:15432 my-ecs
```

隧道建立后，`.env` 使用 `DB_HOST=127.0.0.1`、`DB_PORT=15432`。
验证连接与版本：

```bash
uv run python tests/db_check.py     # 期望输出 SELECT 1 -> 1 与 openGauss 版本
```

### 2.2 初始化表结构

```bash
uv run python tests/schema_check.py  # 应用 schema.sql 并验证约束（幂等，不删数据）
```

6 张表建在专用 schema `steam` 内（`steam_app` 对共享 `public` 无建表权限）。
设计说明与 E-R 图见 [`database/SCHEMA.md`](database/SCHEMA.md)。

### 2.3 启动

```bash
uv run python app.py
# 浏览器访问 http://127.0.0.1:5000
```

首页会重定向到游戏库。四个页面：`/library`、`/purchases`、`/dashboard`、`/analytics`。

## 3. 测试与验证脚本

```bash
uv run pytest              # 单元测试 + 静态一致性检查（不需要数据库）
uv run ruff check .        # 静态检查
```

需要真实数据库的验证脚本（每个都会在结束时清理自己创建的测试数据）：

| 脚本 | 验证内容 |
|---|---|
| `tests/db_check.py` | openGauss 连接、`SELECT 1`、服务端版本 |
| `tests/schema_check.py` | 建表、主外键、CHECK、唯一约束真的拒绝非法数据 |
| `tests/sync_check.py` | 首次/重复同步幂等、用户字段保留、失败不清空、批量原子性 |
| `tests/games_api_check.py` | 游戏 CRUD、搜索筛选、隐藏/删除规则 |
| `tests/purchases_check.py` | 购买记录 CRUD、退款/零成本/未知成本口径 |
| `tests/stats_check.py` | 统计口径与 SQL 交叉校验（多题材均分、吃灰、年度） |
| `tests/steam_check.py` | 真实 Steam API（需凭据；未配置时会明确提示） |

## 4. 统计口径（摘要）

完整定义见 `PLAN.md` §7，实现见 `services/stats_service.py`。

- **范围**：统计只覆盖非隐藏游戏。
- **未启动率**：时长 0 的游戏 ÷ 全部可见游戏。
- **未通关率**：分母只含用户明确标记过状态的游戏；`unknown` / `not_applicable` 不计入，
  “状态待确认”单独显示。
- **题材占比**：多题材游戏的时长按题材数均分，避免重复计数；无题材归“未分类”。
- **每小时成本**：仅消费记录完整、净支出 > 0、时长 > 0 的游戏参与；0 时长不参与（不除零）。
- **年度消费**：按购买日期年份分组，退款金额扣除；无日期记录不计入并单独提示。
- **免费 vs 未知**：没有购买记录 **不等于** 0 元。必须由用户标记 `purchase_records_complete`
  才算已知成本。

## 5. openGauss 平台差异（写报告时注意）

| 现象 | 处理 |
|---|---|
| `DATE` 在 A 兼容模式下实为 `timestamp(0)`，不截断时分秒 | 列仍用 `DATE`，另加 `CHECK (purchase_date = date_trunc('day', purchase_date))` 强制日粒度 |
| 不支持 PostgreSQL 的 `ON CONFLICT` | 改用 `ON DUPLICATE KEY UPDATE`（见 `services/sync_service.py`） |
| `steam_app` 对 `public` schema 无 CREATE 权限 | 全部对象放入专用 schema `steam` |

## 6. 安全注意

- `.env` 已在 `.gitignore` 中；版本控制里只有 `.env.example` 占位符。
- Flask 只绑定 `127.0.0.1`。
- 数据库使用专用非超管账户 `steam_app`，不使用 `omm` 超级用户。
- API 错误信息不包含密码或 API Key；已由测试 `test_pages_do_not_leak_credentials` 守护。

## 7. 目录结构

```text
app.py                  启动入口、蓝图注册
config.py               环境变量配置
database/db.py          连接、事务、参数化查询
database/schema.sql     6 张表、约束、索引
database/SCHEMA.md      E-R 图与设计说明
routes/                 games / purchases / statistics / pages
services/               steam_api / sync_service / game_service /
                        purchase_service / stats_service
templates/              base + 四个页面
static/js/              i18n.js（中英字典）+ 各页脚本 + charts.js
static/vendor/          Bootstrap、ECharts（本地化）
tests/                  单元测试 + 真实库验证脚本 + 模拟样本
```

## 8. 报告素材清单

| 材料 | 位置 |
|---|---|
| E-R 图（Mermaid） | `database/SCHEMA.md` §1 |
| 表结构与约束说明 | `database/SCHEMA.md` §2 |
| 建表 SQL | `database/schema.sql` |
| 关键查询（聚合） | `services/stats_service.py` |
| 界面截图 | 运行 `app.py` 后访问四个页面；中英文各截一次 |
| 测试证据 | 第 3 节各脚本的终端输出 |
| 平台差异说明 | 本文 §5 |

## 9. 已知限制（v1.0）

- 购买金额仅支持人民币，不做汇率换算；部分退款不支持。
- Steam API 不提供历史购买金额与日期，需手工补录；无记录时显示“消费未知”。
- Steam 同步不保证覆盖所有未玩过的免费游戏；隐私设置可能导致空结果。
- 题材需手工设置或后续从商店补全，未设置即为“未分类”。
- 同步日志中的失败记录会保留，用于追溯。
