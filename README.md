# trip-agent ✈️

![CI](https://github.com/PakHeiPoon/trip-agent/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-1.x-2ea44f)
![vivo 蓝心](https://img.shields.io/badge/LLM-vivo%20蓝心-5468ff)

觅途 (MustStart) 的旅行规划智能体 —— 基于 **LangGraph** 的 **1+N 多 Agent** 系统，跑在 **vivo 蓝心大模型** 上。

这是「智能体的唯一源头」：既能部署到 **LangGraph Platform** 当在线服务，也能被其他项目当 **Python 包 / git submodule** 引入。

## 架构

```
START → supervisor(总控) ──无需专家──→ finalize(管家) → END
                         └──有需求───→ experts → finalize → END
```

- **总控 supervisor**：用 `with_structured_output` 判断本轮调度哪些专家
- **专家 Agent**（`create_react_agent`，可调真实工具）：
  - `规划 planner` — 行程/路线（工具：`vivo_poi_search`、`get_weather`）
  - `比价 pricing` — 预算/性价比
  - `应急 contingency` — 天气突发改排（工具：`get_weather`）
- **汇总 finalizer**：以"MustStart旅行管家"人格融合专家意见，按需输出 MIP 攻略 JSON
- 工具：vivo POI(`/search/geo`) / vivo OCR(`/ocr/general_recognition`) / 天气(open-meteo)

## 目录

```
agent/        # 智能体核心：graph / llm(vivo) / state / tracing / tools
prompts/      # supervisor / 专家 / 旅行规划 system prompts
langgraph.json # LangGraph Server / Platform 入口 (-> agent/graph.py:make_graph)
```

## 本地开发

```bash
uv sync
cp .env.example .env           # 填入 VIVO_API_KEY 等

# 方式一：FastAPI HTTP 服务（提供 /api/chat，线上部署用的就是它）
uv run --extra server uvicorn server:app --port 8000

# 方式二：LangGraph Server + Studio（可视化调试多 Agent 图）
uv run langgraph dev --allow-blocking

uv run pytest -m "not integration"      # 离线测试
```

## HTTP 接口（部署后对外提供）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 → `{"status":"ok"}` |
| POST | `/api/chat` | 旅行对话。请求 `{message, session_id?, context_guide?}` → 响应 `{session_id, reply, guide_json?}` |

```bash
curl -X POST http://<host>:8800/api/chat -H 'Content-Type: application/json' \
  -d '{"message":"我想去成都玩3天"}'
# → {"session_id":"...","reply":"...","guide_json":null}
```

> `guide_json` 在攻略规划完整时为结构化攻略（MIP `TravelGuideSchema`），规划中为 `null`。

## 部署

**自托管 Docker（当前线上用这个）**：在本机跑 `./deploy.sh`（rsync 上传 + 远程 `docker build`/`run`，监听 8800）。详见 `deploy.sh` 顶部说明。

**LangGraph Platform（备选，云托管）**：LangSmith → Deployments → New → 选本仓库 + 分支（`langgraph.json` 在根目录）→ 填环境变量 → 得到 `https://xxx.langgraph.app` + 云端 Studio。

## 环境变量

| 变量 | 必须 | 说明 |
|---|---|---|
| `VIVO_API_KEY` | ✅ | vivo AppKey（`sk-xuanji-...`，Bearer 鉴权） |
| `VIVO_APP_ID` | OCR 需要 | 数字 AppId，OCR 的 `businessid="aigc"+AppId` |
| `VIVO_MODEL` | 否 | 默认 `Volc-DeepSeek-V3.2` |
| `VIVO_REASONING_EFFORT` | 否 | 默认 `low` |
| `LANGSMITH_API_KEY` | 否 | 链路追踪（Platform 上自动配置） |
| `CHECKPOINT_DB` | 否 | 会话持久化 sqlite 路径，默认 `data/checkpoints.sqlite` |

## 会话持久化

FastAPI 路径用 **SqliteSaver** 把每个会话（`thread_id` = `session_id`）的对话持久化到 sqlite，**重启/重新部署都不丢上下文**。
Docker 部署务必把 DB 目录挂成 volume（`deploy.sh` 已加 `-v .../data:/app/data`），否则容器重建会清掉容器内文件。
（`langgraph dev` / LangGraph Platform 路径由平台自管持久化，`make_graph()` 不带 checkpointer。）

## 被其他项目引用的两种方式

**A. 调用在线服务**（推荐解耦）：
```python
from langgraph_sdk import get_sync_client
client = get_sync_client(url="https://xxx.langgraph.app", api_key="<langsmith-key>")
thread = client.threads.create()
result = client.runs.wait(thread["thread_id"], "muststart",
                          input={"messages": [{"role": "user", "content": "成都3天"}]})
```

**B. 当包 / 子模块装进来**：
```bash
pip install "git+ssh://git@github.com/<you>/trip-agent.git"
```
```python
from agent.graph import graph
result = graph.invoke({"messages": [("user", "成都3天")]},
                      config={"configurable": {"thread_id": "t1"}})
```
