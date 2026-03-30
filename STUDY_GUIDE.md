# Learn Claude Code 完整学习指南

> **目标读者**：想要深入理解 AI Agent 工程（Harness Engineering）的开发者
> **预计总学时**：40-60 小时（建议 4-6 周完成）
> **前置要求**：Python 基础、了解 HTTP API 调用、基本 Git 操作

---

## 一、项目全景：你将学到什么

这个项目通过 **12 个递进式课程（s01-s12）**，从零教你构建一个完整的 AI 编程 Agent。

核心理念：**模型就是 Agent，代码是 Harness（驾驭层）**。你不是在"开发 AI"，你是在为 AI 构建一个可以工作的环境。

```
代码量增长路线：

s01  119 行  ████
s02  151 行  █████
s03  212 行  ███████
s04  185 行  ██████
s05  228 行  ████████
s06  255 行  █████████
s07  244 行  ████████
s08  235 行  ████████
s09  404 行  ██████████████
s10  485 行  █████████████████
s11  587 行  ████████████████████
s12  783 行  ███████████████████████████

s_full (总纲) 741 行
```

### 架构层级图

```
┌─────────────────────────────────────────────────────────────┐
│                    第四阶段: 协作与隔离                         │
│  ┌───────────┐  ┌──────────────┐  ┌──────────┐  ┌────────┐ │
│  │ s09 团队   │→│ s10 团队协议  │→│ s11 自治  │→│s12 隔离│ │
│  │ JSONL邮箱  │  │ 关机+审批FSM │  │ 自动认领  │  │worktree│ │
│  └───────────┘  └──────────────┘  └──────────┘  └────────┘ │
├─────────────────────────────────────────────────────────────┤
│                    第三阶段: 持久化与并发                       │
│  ┌───────────────────────┐  ┌───────────────────────┐       │
│  │ s07 任务系统            │  │ s08 后台任务            │       │
│  │ 磁盘持久化 + 依赖图      │  │ 守护线程 + 通知队列      │       │
│  └───────────────────────┘  └───────────────────────┘       │
├─────────────────────────────────────────────────────────────┤
│                    第二阶段: 规划与知识                         │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │s03 规划  │→│s04 子Agent│→│s05 Skills │→│s06 上下文压缩│  │
│  │TodoWrite │  │上下文隔离  │  │按需加载   │  │三层压缩策略  │  │
│  └─────────┘  └──────────┘  └──────────┘  └─────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    第一阶段: 循环与工具                         │
│  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │ s01 Agent Loop    │→│ s02 Tool Use                     │ │
│  │ while+stop_reason │  │ dispatch map + 路径沙箱            │ │
│  └──────────────────┘  └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、学习周期规划（4-6 周）

### 第 1 周：地基 — 循环与工具（s01-s02）

#### Day 1-2：s01 - Agent Loop（核心中的核心）

**学习目标**：理解 AI Agent 的最小可运行单元

**要掌握的核心概念**：
1. `while True` 循环 — Agent 的心跳
2. `stop_reason == "tool_use"` — 模型自己决定何时调用工具、何时停止
3. `messages[]` — 对话历史就是 Agent 的全部记忆
4. 单工具 `bash` — 一个工具就能让 Agent 做任何事

**学习步骤**：

```
步骤 1: 阅读理论（30 分钟）
    → 阅读 README-zh.md 的 "模型就是 Agent" 章节
    → 理解 Agent vs Harness 的哲学区别

步骤 2: 阅读源码（1 小时）
    → 打开 agents/s01_agent_loop.py
    → 逐行阅读，标注以下关键结构：
      - SYSTEM_PROMPT: 告诉模型它是谁、能做什么
      - TOOLS: JSON Schema 定义工具接口
      - agent_loop(): 核心循环函数
      - main(): 用户输入 → 循环 → 输出

步骤 3: 阅读文档（30 分钟）
    → 阅读 docs/zh/s01-the-agent-loop.md
    → 重点关注 ASCII 架构图和变更对照表

步骤 4: 动手实验（2 小时）
    → 配置好 .env 中的 API Key
    → 运行: python3 agents/s01_agent_loop.py
    → 实验 1: 让 Agent 用 bash 查看目录结构
    → 实验 2: 让 Agent 创建一个文件
    → 实验 3: 让 Agent 完成一个多步骤任务，观察它如何自主决策
    → 实验 4: 在代码中加 print 打印每轮的 messages 长度和 stop_reason

步骤 5: 手绘笔记（30 分钟）
    → 画出 Agent Loop 的流程图
    → 标注 messages[] 在每一轮是如何增长的
```

**关键代码片段（必须能默写）**：

```python
def agent_loop(messages):
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM,
            messages=messages, tools=TOOLS,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return  # 模型决定停止

        results = []
        for block in response.content:
            if block.type == "tool_use":
                output = TOOL_HANDLERS[block.name](**block.input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                })
        messages.append({"role": "user", "content": results})
```

**检验标准**：
- [ ] 能脱口而出 Agent Loop 的三个核心要素
- [ ] 能解释为什么 `stop_reason` 是模型而非代码决定的
- [ ] 成功运行并完成至少 3 个实验

---

#### Day 3-4：s02 - Tool Use（工具分发）

**学习目标**：理解如何在不改循环的情况下扩展 Agent 能力

**要掌握的核心概念**：
1. `TOOL_HANDLERS` dispatch map — 工具名 → 处理函数的映射
2. 路径沙箱 `safe_path()` — 防止 Agent 访问不该访问的文件
3. 4 个基础工具：`bash`, `read_file`, `write_file`, `edit_file`
4. JSON Schema 工具定义 — 模型通过 Schema 理解工具的输入输出

**学习步骤**：

```
步骤 1: 对比 s01 和 s02 的差异（1 小时）
    → 用 diff 工具对比两个文件
    → 重点关注：循环代码有没有变？（答案：没有！）
    → 理解：加工具 = 加 handler + 加 Schema，循环不动

步骤 2: 深入源码（1 小时）
    → 研究 safe_path() 的实现逻辑
    → 研究 edit_file 工具的 old_str/new_str 替换机制
    → 理解每个工具的 JSON Schema 定义

步骤 3: 动手实验（2 小时）
    → 运行: python3 agents/s02_tool_use.py
    → 实验 1: 让 Agent 读取一个文件，然后修改它
    → 实验 2: 尝试让 Agent 访问沙箱外的文件，观察 safe_path 的拦截
    → 实验 3（挑战）: 自己添加一个新工具（比如 list_directory）
      - 只需要: ① 写 handler 函数 ② 写 JSON Schema ③ 注册到 dispatch map
```

**检验标准**：
- [ ] 能解释 dispatch map 模式的优势
- [ ] 成功给 Agent 添加了一个自定义工具
- [ ] 能解释为什么路径沙箱是必须的安全机制

---

#### Day 5：第一周复盘

```
复盘清单：
1. 画出 s01 → s02 的架构演进图
2. 回答：为什么 Agent Loop 从 s01 到 s12 循环代码始终不变？
3. 回答：如果要给 Agent 加一个「发送 HTTP 请求」的工具，需要改哪些地方？
4. 把你的学习笔记整理成文档，推送到你的 GitHub 仓库
```

---

### 第 2 周：大脑升级 — 规划与知识（s03-s06）

#### Day 1-2：s03 - TodoWrite（任务规划）

**学习目标**：理解为什么 Agent 需要显式的任务规划

**核心概念**：
1. `TodoManager` — 管理待办项的状态机（pending → in_progress → completed）
2. 同一时间只允许 1 个 `in_progress` 任务 — 聚焦策略
3. **Nag Reminder** — 3 轮未更新 todo 则注入 `<reminder>` 提醒
4. 工具数量从 4 → 5（新增 `todo_write`）

**学习步骤**：

```
步骤 1: 理解问题（30 分钟）
    → 思考：没有规划的 Agent 会怎样？（走哪算哪，遗漏步骤）
    → 阅读 docs/zh/s03-todo-write.md

步骤 2: 源码精读（1 小时）
    → 重点关注 TodoManager 类的状态管理
    → 理解 nag_reminder 的注入时机和方式
    → 观察：system prompt 中如何告诉模型使用 todo

步骤 3: 动手实验（2 小时）
    → 运行: python3 agents/s03_todo_write.py
    → 实验 1: 给 Agent 一个复杂任务（如"创建一个包含 3 个文件的项目"）
    → 观察 Agent 是否先创建 todo，再逐步执行
    → 实验 2: 故意在 3 轮内不让 Agent 更新 todo，观察 reminder
```

**关键设计模式**：

```
messages[] 注入策略:
    ┌─────────────┐
    │ 每次 LLM 调用前│
    │ 检查 todo 状态 │
    │     ↓         │
    │ 3 轮未更新?   │──是──→ 注入 <reminder> 到 messages
    │     ↓ 否      │
    │ 正常继续      │
    └─────────────┘
```

---

#### Day 3：s04 - Subagent（子 Agent 隔离）

**学习目标**：理解如何用隔离的上下文处理复杂子任务

**核心概念**：
1. 子 Agent = 独立的 `messages[]` — 不污染主对话
2. 子 Agent 完成后只返回文本摘要，上下文被丢弃
3. 子 Agent 不能递归派生（防止失控）
4. `run_subagent()` 函数 — 以空 messages 启动新循环

**学习步骤**：

```
步骤 1: 理解问题（30 分钟）
    → 如果所有子任务都在主对话中执行，messages[] 会爆炸
    → 子任务的细节不需要保留，只需要结果

步骤 2: 源码精读 + 实验（2 小时）
    → 对比 s03 和 s04 的差异
    → 运行实验：让 Agent 派生子任务
    → 观察主 Agent 和子 Agent 的 messages 分别有多长
```

**关键架构**：

```
主 Agent messages[]
    ├── 用户消息
    ├── 助手回复 (tool_use: task)
    ├── tool_result: "子任务摘要文本"    ← 只有摘要回来
    └── 助手继续工作...

子 Agent messages[]（临时）
    ├── 子任务描述
    ├── 助手执行...
    ├── 工具调用...
    └── 最终回复 → 被提取为摘要文本
        ↑ 执行完毕后整个 messages[] 被丢弃
```

---

#### Day 4：s05 - Skill Loading（技能按需加载）

**学习目标**：理解如何让 Agent 按需获取领域知识

**核心概念**：
1. **两层注入策略**：
   - Layer 1: system prompt 中放技能名和简介（~100 token/skill）
   - Layer 2: 通过 `tool_result` 注入完整技能内容
2. `SkillLoader` 类 — 扫描 `skills/*/SKILL.md` 目录
3. YAML frontmatter — 每个 SKILL.md 的元数据（name + description）
4. 为什么不直接塞 system prompt？因为 token 有限，大部分知识用不到

**学习步骤**：

```
步骤 1: 研究 skills/ 目录结构（30 分钟）
    → 查看 4 个技能：agent-builder, code-review, mcp-builder, pdf
    → 阅读每个 SKILL.md 的 frontmatter 和内容

步骤 2: 源码精读 + 实验（2 小时）
    → 理解 SkillLoader 的扫描机制
    → 运行 s05，让 Agent 加载一个技能
    → 观察 tool_result 中注入了什么内容
```

---

#### Day 5：s06 - Context Compact（上下文压缩）

**学习目标**：理解如何让 Agent 在有限的上下文窗口内持续工作

**核心概念 — 三层压缩策略**：

```
层级 1: micro_compact（静默替换）
    每轮结束后，自动将旧的 tool_result 替换为
    "[已处理: <tool_name> 的输出已被压缩]"

层级 2: auto_compact（自动摘要）
    当 token > 50000 时自动触发：
    ① 保存完整 transcript 到 .transcripts/ 目录
    ② 用 LLM 生成摘要
    ③ 用摘要替换 messages[]

层级 3: compact 工具（手动触发）
    Agent 自己决定何时调用 compact 工具
```

**学习步骤**：

```
步骤 1: 阅读文档（30 分钟）
    → docs/zh/s06-context-compact.md

步骤 2: 源码精读（1 小时）
    → 理解三个压缩函数的触发条件和实现
    → 关注 .transcripts/ 目录的持久化策略

步骤 3: 实验（1.5 小时）
    → 给 Agent 一个非常长的任务
    → 在代码中加 print 打印每轮的 token 估算值
    → 观察 micro_compact 和 auto_compact 的触发
```

#### Day 5 也是：第二周复盘

```
复盘清单：
1. 画出 s03-s06 每个机制的数据流向图
2. 回答：为什么 Skill 用 tool_result 注入而不是放在 system prompt？
3. 回答：三层压缩中，哪一层是最关键的？为什么？
4. 回答：子 Agent 的上下文隔离解决了什么问题？有什么代价？
5. 挑战：修改 s06，把 auto_compact 的阈值从 50000 改成 30000，观察行为变化
```

---

### 第 3 周：持久化与并发（s07-s08）

#### Day 1-3：s07 - Task System（任务系统）

**学习目标**：理解如何把任务持久化到磁盘并建立依赖关系

**核心概念**：
1. `TaskManager` — 任务 CRUD 管理器
2. `.tasks/task_N.json` — 每个任务一个 JSON 文件
3. **依赖图**：`blockedBy` 字段定义前置任务
4. 完成任务时自动解锁下游任务（`blocked` → `pending`）
5. 4 个新工具：`task_create`, `task_update`, `task_list`, `task_get`

**学习步骤**：

```
步骤 1: 理解 todo 和 task 的区别（30 分钟）
    → todo (s03): 内存中，单次对话有效
    → task (s07): 磁盘持久化，跨对话有效，支持依赖关系

步骤 2: 源码精读（1.5 小时）
    → 重点关注 TaskManager 的 create/complete 方法
    → 理解 blockedBy 的解析和解锁逻辑
    → 查看 .tasks/ 目录下 JSON 文件的格式

步骤 3: 实验（2 小时）
    → 运行 s07，创建一个有依赖关系的任务图：
      task A (无依赖)
      task B (依赖 A)
      task C (依赖 A, B)
    → 观察完成 A 后，B 的状态变化
    → 查看 .tasks/ 目录下生成的文件
```

**任务依赖图示例**：

```
task_1 [设计 API]
    ↓
task_2 [实现后端] ──blockedBy: [1]
    ↓
task_4 [集成测试] ──blockedBy: [2, 3]
    ↑
task_3 [实现前端] ──blockedBy: [1]

完成 task_1 → task_2 和 task_3 自动从 blocked → pending
完成 task_2 和 task_3 → task_4 自动从 blocked → pending
```

---

#### Day 4-5：s08 - Background Tasks（后台任务）

**学习目标**：理解如何让 Agent 异步处理耗时操作

**核心概念**：
1. `BackgroundManager` — 管理后台线程
2. 守护线程（daemon thread）执行耗时命令
3. 通知队列（notification queue）— 完成后注入结果
4. 每次 LLM 调用前排空通知队列

**学习步骤**：

```
步骤 1: 理解问题（30 分钟）
    → 如果 Agent 运行一个耗时 30 秒的命令
    → 同步执行：Agent 卡死 30 秒
    → 异步执行：立即返回 task_id，Agent 可以继续做其他事

步骤 2: 源码精读（1 小时）
    → 关注 threading.Thread(daemon=True) 的使用
    → 理解通知队列的注入时机

步骤 3: 实验（1.5 小时）
    → 运行 s08
    → 让 Agent 执行一个 "sleep 10 && echo done" 的后台命令
    → 观察 Agent 是否在等待期间继续响应
```

---

### 第 4 周：团队协作基础（s09-s10）

#### Day 1-3：s09 - Agent Teams（Agent 团队）

**学习目标**：理解如何让多个 Agent 协作

**这是一个重要的复杂度跳跃**——代码量从 235 行跳到 404 行。

**核心概念**：
1. `TeammateManager` — 管理命名队友的生命周期
2. 每个队友在独立线程中运行完整 agent loop
3. `MessageBus` — 基于 JSONL 文件的 append-only 收件箱
4. 消息格式：`{from, to, content, timestamp}`
5. 9 个工具（从 s08 的 6 个跳到 9 个）

**学习步骤**：

```
步骤 1: 理解架构（1 小时）
    → 画出主 Agent + 队友 Agent 的线程关系
    → 理解 JSONL 邮箱的读写机制

步骤 2: 源码精读（2 小时）
    → TeammateManager.spawn() — 如何创建队友
    → MessageBus — 如何通过文件系统通信
    → 每个队友的 agent_loop 是如何在线程中运行的

步骤 3: 实验（2 小时）
    → 运行 s09
    → 创建一个队友，让它负责"搜索文件"
    → 主 Agent 负责"整理结果"
    → 观察邮箱文件的内容变化
```

**邮箱架构**：

```
.mailboxes/
├── main.jsonl           ← 主 Agent 的收件箱
├── researcher.jsonl     ← researcher 队友的收件箱
└── coder.jsonl          ← coder 队友的收件箱

每条消息是一行 JSON:
{"from":"main","to":"researcher","content":"请搜索...","ts":"2025-..."}
{"from":"researcher","to":"main","content":"找到了...","ts":"2025-..."}
```

---

#### Day 4-5：s10 - Team Protocols（团队协议）

**学习目标**：理解结构化的团队协商机制

**核心概念**：
1. **关机协议**：request → response，通过 `request_id` 关联
2. **计划审批协议**：提交计划 → 批准/拒绝
3. 共享 FSM（有限状态机）：`pending` → `approved` / `rejected`
4. 工具数量增至 12 个

**学习步骤**：

```
步骤 1: 理解 FSM 状态转换（1 小时）
    → 画出关机协议的状态图
    → 画出计划审批的状态图

步骤 2: 源码精读（1.5 小时）
    → 关注 request_id 的生成和匹配
    → 理解 pending → approved/rejected 的转换条件

步骤 3: 实验（2 小时）
    → 运行 s10
    → 模拟一个关机协商流程
    → 模拟一个计划审批流程
```

---

### 第 5 周：自治与隔离（s11-s12）

#### Day 1-3：s11 - Autonomous Agents（自治 Agent）

**这是理解上最难的一课**——Agent 从被动执行变为主动寻找工作。

**核心概念**：
1. **WORK/IDLE 两阶段循环**：
   - WORK 阶段：正常执行任务
   - IDLE 阶段：每 5 秒轮询收件箱和任务板
2. 自动认领未分配任务
3. 60 秒无任务自动关机
4. 压缩后身份重注入（防止 Agent 忘记自己是谁）
5. 工具数量增至 14 个

**学习步骤**：

```
步骤 1: 理解两阶段循环（1 小时）
    WORK 阶段:
    ┌──────────────────────────────┐
    │  正常 agent loop              │
    │  有任务 → 执行                │
    │  任务完成 → 切换到 IDLE       │
    └──────────────────────────────┘
              ↕
    IDLE 阶段:
    ┌──────────────────────────────┐
    │  每 5s 检查:                  │
    │  - 收件箱有新消息？→ 切回 WORK│
    │  - 任务板有未认领任务？→ 认领  │
    │  - 60s 无事可做？→ 自动关机   │
    └──────────────────────────────┘

步骤 2: 源码精读（2 小时）
    → idle 工具的实现
    → 任务认领的逻辑
    → 身份重注入的时机

步骤 3: 实验（2 小时）
    → 运行 s11，创建 2 个自治队友
    → 在任务板上放几个任务
    → 观察队友是否自动认领并执行
```

---

#### Day 4-5：s12 - Worktree Task Isolation（Worktree 隔离）

**课程的终极形态**——783 行代码，16 个工具。

**核心概念**：
1. `WorktreeManager` — 基于 git worktree 的目录隔离
2. 每个任务绑定独立的工作目录
3. `EventBus` — 生命周期事件记录到 `.worktrees/events.jsonl`
4. 完成后可以 `keep`（保留）或 `remove + complete_task`（清理）

**学习步骤**：

```
步骤 1: 理解 git worktree（30 分钟）
    → git worktree 是 git 的原生功能
    → 允许同一仓库有多个工作目录
    → 每个目录可以在不同的分支上独立工作

步骤 2: 理解为什么需要隔离（30 分钟）
    → 多个 Agent 同时工作
    → 如果共享同一目录 → 文件冲突、互相覆盖
    → 每个任务分配独立 worktree → 互不干扰

步骤 3: 源码精读（2 小时）
    → WorktreeManager 的 create/bind/remove 方法
    → EventBus 的事件格式
    → 任务 ID 和 worktree 的绑定关系

步骤 4: 实验（2 小时）
    → 在一个 git 仓库中运行 s12
    → 创建 2 个任务，观察 worktree 目录的创建
    → 完成任务后观察 worktree 的清理
```

**Worktree 隔离架构**：

```
my-project/                      ← 主仓库
├── .git/
├── .worktrees/
│   ├── events.jsonl             ← 生命周期事件流
│   ├── task_1/                  ← 任务 1 的独立工作目录
│   │   ├── .git → ../../.git   (共享 git 对象)
│   │   └── (独立的文件树)
│   └── task_2/                  ← 任务 2 的独立工作目录
│       ├── .git → ../../.git
│       └── (独立的文件树)
└── src/                         ← 主仓库文件
```

---

### 第 6 周：总纲与实战

#### Day 1-2：s_full.py — 全部机制合一

**学习目标**：理解 12 个机制如何在 741 行代码中和谐共存

**学习步骤**：

```
步骤 1: 通读 s_full.py（2 小时）
    → 不需要逐行精读，重点关注:
    → 22 个工具的注册列表
    → 各 Manager 类的初始化顺序
    → REPL 的 /compact /tasks /team /inbox 命令

步骤 2: 实验 — 全功能体验（3 小时）
    → 运行: python3 agents/s_full.py
    → 综合实验：给 Agent 一个完整项目任务
    → 观察它如何：
      ① 创建 todo 规划步骤
      ② 派生子 Agent 处理子任务
      ③ 加载技能获取知识
      ④ 压缩上下文保持窗口干净
      ⑤ 创建持久化任务
      ⑥ 协调团队完成协作
```

#### Day 3-5：实战项目

选择一个实战方向，巩固所学：

**方向 A：改造现有 Agent（推荐新手）**
```
1. 给 s02 添加一个 HTTP 请求工具
2. 修改 s06 的压缩策略参数，测试不同阈值的效果
3. 给 s07 的任务系统添加优先级字段
```

**方向 B：构建领域 Agent（推荐有经验者）**
```
1. 参考 s_full.py 的架构
2. 选择一个领域（如：文档翻译、数据分析、代码审查）
3. 设计领域特定的工具集
4. 实现最小可用版本
```

**方向 C：深入 Web 平台**
```
1. 启动 web 平台: cd web && npm run dev
2. 阅读每个可视化组件的实现
3. 尝试给某个课程添加新的交互式动画
```

---

## 三、每日学习流程模板

```
┌──────────────────────────────────────────┐
│ 每课学习流程 (约 4-5 小时)                 │
│                                          │
│ 1. 阅读文档 docs/zh/sXX-*.md  (30 min)   │
│    → 理解问题和解决方案                     │
│                                          │
│ 2. 精读源码 agents/sXX_*.py   (1-1.5 hr) │
│    → 对比上一课的 diff                     │
│    → 标注新增代码                          │
│                                          │
│ 3. 动手实验                    (1.5-2 hr) │
│    → 运行代码                             │
│    → 完成文档末尾的「试一试」实验           │
│    → 修改参数观察行为变化                   │
│                                          │
│ 4. 画笔记                      (30 min)   │
│    → 画出本课新增机制的数据流图             │
│    → 写下 3 个关键理解点                   │
│                                          │
│ 5. 回顾                        (15 min)   │
│    → 不看代码，口述本课核心逻辑             │
│    → 回答：这个机制解决了什么问题？         │
└──────────────────────────────────────────┘
```

---

## 四、Web 学习平台使用指南

```sh
cd web && npm run dev   # 访问 http://localhost:3000
```

平台提供 5 种学习视图：

| 视图 | 路径 | 用途 |
|------|------|------|
| 首页 | `/zh/` | 项目概览、核心模式动画、学习路径入口 |
| 时间线 | `/zh/timeline` | 12 课程的时间线渐进视图 |
| 层级 | `/zh/layers` | 按 5 个层级分类查看课程 |
| 课程详情 | `/zh/s01` ~ `/zh/s12` | 文档 + 源码 + 可视化 + Diff |
| 版本对比 | `/zh/compare` | 任意两个版本的代码对比 |

**推荐使用方式**：
- 每学一课前，先在 Web 平台上查看对应的可视化动画
- 用 Diff 视图对比相邻两课的代码变化
- 层级视图帮助理解各课程在整体架构中的位置

---

## 五、工具与资源速查

### 运行命令

```sh
# 单课程运行
python3 agents/s01_agent_loop.py
python3 agents/s02_tool_use.py
# ... s03 到 s12 类推
python3 agents/s_full.py          # 全部机制合一

# Web 平台
cd web && npm run dev

# 测试
python3 -m pytest tests/ -v
```

### 文件速查

| 要找什么 | 去哪里 |
|----------|--------|
| 第 N 课源码 | `agents/sN_*.py` |
| 第 N 课文档 | `docs/zh/sN-*.md` |
| 技能文件 | `skills/*/SKILL.md` |
| Web 可视化组件 | `web/src/components/visualizations/` |
| 课程元数据 | `web/src/lib/constants.ts` |

### 关键概念对照表

| 概念 | 首次出现 | 说明 |
|------|----------|------|
| Agent Loop | s01 | `while True` + `stop_reason` 退出 |
| Dispatch Map | s02 | 工具名 → 处理函数的映射 |
| TodoManager | s03 | 内存中的任务状态管理 |
| Subagent | s04 | 隔离上下文的子 Agent |
| SkillLoader | s05 | 按需加载领域知识 |
| 三层压缩 | s06 | micro/auto/manual 压缩策略 |
| TaskManager | s07 | 磁盘持久化的任务图 |
| BackgroundManager | s08 | 守护线程异步执行 |
| TeammateManager | s09 | 命名队友 + JSONL 邮箱 |
| 关机/审批协议 | s10 | request-response FSM |
| WORK/IDLE 循环 | s11 | 自治 Agent 的两阶段 |
| WorktreeManager | s12 | git worktree 目录隔离 |

---

## 六、常见问题

### Q: 我需要有 Anthropic API Key 才能运行吗？
A: 是的。但 `.env.example` 中列出了多个兼容提供商（MiniMax、GLM、Kimi、DeepSeek），国内可直接使用。

### Q: 可以跳课学习吗？
A: 不建议。每课只在前一课基础上添加一个机制，跳过会导致理解断层。唯一例外是 s07 和 s08 相对独立，可以调换顺序。

### Q: s_full.py 和 s12 的关系是什么？
A: `s_full.py` 集成了 s01-s11 的全部机制（741 行），是可直接使用的"总纲"。s12 因为引入了 git worktree 的外部依赖，作为独立的进阶课程存在。

### Q: 最重要的 3 课是哪些？
A: **s01**（理解循环本质）、**s06**（上下文管理是生产环境的核心挑战）、**s09**（多 Agent 协作是未来方向）。

### Q: 学完之后下一步做什么？
A: 三个方向：
1. 用 [Kode CLI](https://github.com/shareAI-lab/Kode-cli) 体验生产级实现
2. 用 [Kode SDK](https://github.com/shareAI-lab/Kode-agent-sdk) 将 Agent 嵌入你的应用
3. 学习姊妹项目 [claw0](https://github.com/shareAI-lab/claw0)，理解常驻式 Agent
