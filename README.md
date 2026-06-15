# trip-agent ✈️

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
uv run langgraph dev --allow-blocking   # 启动 LangGraph Server + Studio
uv run pytest -m "not integration"      # 离线测试
```

## 部署到 LangGraph Platform（在线）

1. 把本仓库推到 GitHub
2. LangSmith → **Deployments** → New → 选本仓库 + 分支，`langgraph.json` 在根目录
3. 在部署设置里填环境变量（见下表）
4. 部署完成后得到公网 URL `https://xxx.langgraph.app` + 云端 Studio

## 环境变量

| 变量 | 必须 | 说明 |
|---|---|---|
| `VIVO_API_KEY` | ✅ | vivo AppKey（`sk-xuanji-...`，Bearer 鉴权） |
| `VIVO_APP_ID` | OCR 需要 | 数字 AppId，OCR 的 `businessid="aigc"+AppId` |
| `VIVO_MODEL` | 否 | 默认 `Volc-DeepSeek-V3.2` |
| `VIVO_REASONING_EFFORT` | 否 | 默认 `low` |
| `LANGSMITH_API_KEY` | 否 | 链路追踪（Platform 上自动配置） |

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
