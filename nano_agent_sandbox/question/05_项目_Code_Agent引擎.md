# 项目经历 — Code Agent 智能代码执行引擎 面试题

---

## 一、项目动机 & 定位（了解性）

### Q1: 为什么做这个项目？和你的实习工作有什么关系？

**答案**：
实习中我用 Go 做了生产级的沙箱引擎，但很多 Agent 运行时的核心概念被 AGS SDK 封装了——比如 ReAct 循环怎么驱动、工具路由怎么做、上下文窗口满了怎么办、LLM 返回格式不可控怎么处理。为了**深入理解每个环节的设计决策**，我用 Python 从零实现了一个 mini 版本。这让我在实习中能更好地理解 SDK 的设计意图，也能提出更合理的架构方案。

**建议**：一定要把动机和实习关联起来，说"为了更好地做实习工作"而不是"闲着没事做"。

---

### Q2: 为什么不用 LangChain / CrewAI 这些现成框架？

**答案**：
项目目标是**理解 Agent 运行时的每一个环节**，而非快速搭 demo。手写代码量约 1500 行，每个组件的设计决策（为什么这么分层、为什么这样路由、为什么这样处理错误）都是可解释的。如果用框架，这些权衡被封装了就看不到了。

类比：就像学数据库不能只会用 MySQL CLI，要自己实现一个 mini DB 才能真正理解 B+ 树为什么这么设计。

**建议**：这个问题一定会被问到，回答要自信——"我是为了深度理解，不是不会用框架"。

---

### Q3: 整个项目的架构是什么？分了几层？

**答案**：
五层架构，从上到下：
```
Layer 1: Agent Loop   — ReAct 主循环（Observe→Think→Act→Reflect）
Layer 2: LLM Client   — 流式 LLM 调用 + Action 解析
Layer 3: Tool System   — 工具注册 + O(1) 路由 + 5 个内置工具
Layer 4: Sandbox       — 子进程代码执行 + 文件系统安全管理
Layer 5: Self-Heal     — 错误分类 + 修复建议 + 重试策略
```

每层职责单一、可独立测试、可独立替换。比如 Sandbox 层可以从 subprocess 换成 Docker，不影响上层。

**建议**：分层的核心价值是**可替换性和可测试性**，面试官最爱追问"为什么这么分"。

---

## 二、ReAct 循环（核心 — 深度题）

### Q4: ReAct 循环的每一步具体做什么？代码怎么实现的？

**答案**：
```python
def run(self, user_input: str) -> str:
    self.context.append_user(user_input)   # Observe: 追加用户输入
    for turn in range(MAX_TURNS):          # 最大 25 轮
        action = self._think_stream()       # Think: 流式调 LLM
        results = self._act(action)         # Act: 执行工具/代码
        if action.is_final:                 # 无工具调用 = 最终回复
            return action.text
        should_continue = self._reflect(results)  # Reflect: 错误检测+自愈
        if not should_continue:
            break
    return "达到最大轮次..."
```

- **Observe**：用户输入追加到上下文消息列表
- **Think**：流式调 LLM，实时打印文本，解析返回的 Action（tool_calls / 代码块 / 纯文本）
- **Act**：通过 ToolRegistry dispatch 执行工具，结果追加到上下文
- **Reflect**：检查执行结果是否有错误，有则触发自愈

**建议**：能手写核心循环的伪代码，面试官印象会非常好。

---

### Q5: `is_final` 怎么判断？LLM 什么时候认为任务完成了？

**答案**：
判断逻辑：**如果 LLM 的回复中没有任何 tool_calls 且没有代码块，则认为是最终回复**。

原理：在 function calling 模式下，LLM 认为需要做事时会返回 tool_calls；认为任务完成了会返回纯文本总结。这是 OpenAI API 的标准行为——Agent 自主决策何时停止。

边界情况：
- LLM 忘记调工具（幻觉直接给答案）：CodeAct 降级会尝试提取代码块执行
- LLM 无限循环调工具：25 轮硬上限兜底

**建议**：这个问题很好，体现了你对 Agent "什么时候停"的理解。

---

### Q6: 25 轮硬上限到了怎么办？直接报错吗？

**答案**：
不是直接报错，而是在第 25 轮时**注入终止提示**：
```
"You have reached the maximum number of turns. Please provide a final summary."
```
让 LLM 有机会做总结性回复，而非戛然而止。这样用户至少能看到"我尝试了什么、进展到哪步、还剩什么没完成"。

**建议**：这个细节体现了"用户体验优先"的思维——即使系统要中断，也要给用户一个交代。

---

## 三、CodeAct 降级机制（亮点 — 深度题）

### Q7: 什么是 CodeAct 降级？为什么需要它？

**答案**：
**问题**：LLM 不总是乖乖用 function calling。有些模型（尤其是小模型）或某些场景下，LLM 会直接在文本中写 ` ```python ` 代码块，而非返回结构化的 tool_calls。

**解法**：在 Action 解析时设三级优先级：
1. **优先**检查 `message.tool_calls`（标准 function calling）
2. **降级**用正则 `r"```python\n(.*?)```"` 从文本中提取代码块
3. **兜底**当纯文本回复（`is_final=True`）

这样无论 LLM 以哪种方式"表达执行意图"，Agent 都能理解并执行。

**建议**：这是项目最有区分度的设计点，面试时要主动提到。

---

### Q8: 正则提取代码块会不会误匹配？LLM 在"解释代码"而非"要求执行"怎么区分？

**答案**：
确实存在误匹配风险。比如 LLM 说"以下是一个示例代码"然后贴了代码块——它可能只是在解释，不是要执行。

**当前处理**：宁可多执行一次（结果可 observe），不可漏执行（用户以为 Agent 不干活）。因为：
- 多执行一次的代价：多消耗一次沙箱资源 + LLM 下一轮看到执行结果后自行调整
- 漏执行的代价：用户等半天没结果，体验很差

**改进方向**：
- 加置信度判断（上下文分析 LLM 是否真的要执行）
- 加用户确认步骤（"要执行这段代码吗？"）

**建议**：先说"当前的权衡"，再说"改进方向"，体现你知道局限性且有思考。

---

### Q9: "工具调用覆盖率从 70% 提升至 95%+"——这个数据怎么测的？

**答案**：
测试方法：准备 50 个测试用例（自然语言任务描述），分别在有/无 CodeAct 降级的情况下运行：
- **无降级**：只接受标准 function calling，约 35/50 个任务的 LLM 返回了 tool_calls = 70%
- **有降级**：function calling + 代码块提取，约 48/50 个任务被成功执行 = 96%
- 剩余 2 个是 LLM 回答纯文本且没有代码块的情况（不需要执行代码的简单问题）

**建议**：数据来源要可验证——"50 个测试用例"是可信的规模，比说"大量测试"更具体。

---

## 四、沙箱安全（深度题）

### Q10: 四层沙箱安全防护具体是什么？每层防什么？

**答案**：
| 层级 | 机制 | 防御目标 |
|------|------|----------|
| 路径沙箱化 | `resolve()` + `is_relative_to()` | 防 `../../etc/passwd` 路径穿越 |
| 环境变量隔离 | 只传 PATH/HOME/TMPDIR/LANG | 防 API Key 等敏感信息泄露 |
| 超时保护 | `subprocess.run(timeout=30)` | 防死循环/恶意占 CPU |
| 输出截断 | 限制 50000 字符 | 防 `print("x"*10**9)` 内存爆炸 |

**建议**：安全是面试重点，四层要能快速说出来。

---

### Q11: `safe_path()` 的实现原理？怎么防路径穿越？

**答案**：
```python
def safe_path(self, path_str: str) -> Path:
    target = (self.workdir / path_str).resolve()  # resolve() 消除 .. 和 symlink
    if not target.is_relative_to(self.workdir):    # 检查是否在沙箱目录内
        raise PermissionError(f"Access denied: {path_str}")
    return target
```

攻击示例：`path_str = "../../etc/passwd"`
- `self.workdir / "../../etc/passwd"` → `/tmp/sandbox/../../etc/passwd`
- `.resolve()` → `/etc/passwd`（消除了 `..`）
- `.is_relative_to("/tmp/sandbox")` → `False`
- 拦截！抛出 PermissionError

**建议**：能手写这段代码 + 解释攻击场景，安全部分就过关了。

---

### Q12: subprocess 沙箱有什么局限性？和 Docker 沙箱相比差在哪？

**答案**：
| 维度 | subprocess | Docker |
|------|-----------|--------|
| 进程隔离 | 独立进程，但共享主机 PID 空间 | 完全隔离的 PID namespace |
| 网络隔离 | 无，可访问主机网络 | 独立网络 namespace |
| 文件系统 | 通过 `safe_path` 软限制 | 独立文件系统（overlay fs） |
| 资源限制 | 只有超时，无内存/CPU 限制 | cgroup 精确控制 CPU/内存 |
| 安全性 | 中等（依赖代码层面防护） | 高（内核级隔离） |

`CodeExecutor` 用了 Facade 模式，预留了替换入口：`executor = CodeExecutor(sandbox)` 中的 `sandbox` 可以从 `SubprocessSandbox` 换成 `DockerSandbox`，上层代码不变。

**建议**：承认局限性，同时说明"设计上已经预留了升级路径"，体现工程远见。

---

### Q13: Bash 工具的危险命令黑名单有哪 7 类？黑名单方案有什么问题？

**答案**：
7 类危险命令：
1. `rm -rf /` — 删除根目录
2. `sudo` — 提权
3. `shutdown` — 关机
4. `reboot` — 重启
5. `mkfs` — 格式化磁盘
6. `dd if=` — 磁盘写入
7. `:(){` — Fork Bomb

黑名单问题：
- **绕过容易**：`r\m -rf /`、`$(echo rm) -rf /`、base64 编码后解码执行等
- **维护成本高**：新的危险命令层出不穷，黑名单永远不完整
- **更好的方案**：白名单模式（只允许 `ls`、`cat`、`pip install` 等安全命令）或直接在沙箱内执行

**建议**：面试官一定会追问黑名单的绕过方式，这是安全面试的标准套路。

---

## 五、自愈机制（深度题）

### Q14: 错误自愈的完整流程是什么？

**答案**：
```
代码执行出错
  → ErrorAnalyzer.classify_error(stderr)  — 分类为 6 大类之一
  → ErrorAnalyzer.suggest_fix(error_info) — 生成针对性修复建议
  → RetryStrategy.should_retry(error)     — 判断是否可重试
  → 可重试：注入 <self_heal> 结构化提示到上下文
  → LLM 下一轮看到错误信息 + 修复建议 → 自动修改代码重试
```

注入的格式：
```xml
<self_heal>
错误类型: import
错误信息: ModuleNotFoundError: No module named 'pandas'
修复建议: 使用 pip install 安装缺失模块，或改用标准库替代
剩余重试: 2
</self_heal>
```

用 XML 标签是为了让 LLM 能清晰区分"系统错误反馈"和"用户对话"。

**建议**：这是项目的第二个核心亮点，面试时要主动展开讲。

---

### Q15: 6 大类错误分别是什么？为什么这么分类？

**答案**：
| 类别 | 示例 | 可重试？ | 修复策略 |
|------|------|---------|----------|
| syntax | SyntaxError, IndentationError | 是 | 检查语法缩进 |
| import | ModuleNotFoundError | 是 | pip install 或换标准库 |
| runtime | TypeError, ValueError, KeyError | 是 | 检查类型/变量/数据 |
| io | FileNotFoundError, PermissionError | 是 | 检查路径/权限 |
| resource | MemoryError, RecursionError | 否 | 直接放弃 |
| timeout | TimeoutError | 否 | 直接放弃 |

分类依据：**可恢复性**
- syntax/import/runtime/io：LLM 修改代码可能修复
- resource/timeout：代码逻辑本身有问题（无限递归/数据量超限），重试无意义

**建议**：分类的核心逻辑是"LLM 能不能通过修改代码修复这个问题"，这个思维方式很重要。

---

### Q16: RetryStrategy 的三重防死循环具体怎么实现？

**答案**：
```python
def should_retry(self, error_info: dict) -> bool:
    # 第 1 重：全局次数上限
    if self.total_retries >= 3:
        return False
    
    # 第 2 重：不可恢复错误直接拒绝
    if error_info['type'] in ('resource', 'timeout'):
        return False
    
    # 第 3 重：同类错误指纹检测
    fingerprint = f"{error_info['name']}:{error_info['message'][:100]}"
    if self.error_counts[fingerprint] >= 2:
        return False  # 同样的错误出现 2 次说明 LLM 没学到教训
    
    self.total_retries += 1
    self.error_counts[fingerprint] += 1
    return True
```

三重保护的含义：
1. **全局上限**：无论什么错误，总共最多重试 3 次
2. **不可恢复**：resource/timeout 类错误一次都不重试
3. **指纹去重**：同样的错误连续出现，说明 LLM 的修复策略无效，继续重试没意义

**建议**：这段代码逻辑清晰、面试时能手写出来加分巨大。

---

### Q17: "syntax/import 类错误基本一次修复"——为什么这两类容易修复？

**答案**：
- **syntax**：SyntaxError 的错误信息非常精确（指出哪一行、什么问题），LLM 看到后几乎 100% 能修正
- **import**：ModuleNotFoundError 告诉你缺什么模块，LLM 要么 `pip install` 安装，要么改用标准库替代，选择明确

而 runtime 错误（如 KeyError）的修复率较低，因为需要理解数据结构和逻辑上下文，LLM 可能猜错修复方向。

**建议**：区分"信息充分→容易修复"和"信息不足→难修复"，体现你对 LLM 能力边界的理解。

---

## 六、上下文管理（深度题）

### Q18: 上下文压缩是怎么触发的？压缩算法是什么？

**答案**：
触发条件：`_estimate_tokens()` > 60000 字符

压缩算法：
1. 保留最近 6 条消息（保证当前任务的工具调用结果可见）
2. 旧消息的压缩有两种方式：
   - **有 LLM 可用**：将旧消息发给 LLM，让它生成 3-5 条关键摘要
   - **LLM 不可用/降级**：提取每条旧消息的前 200 字符拼接
3. 压缩后的摘要替换为一条 `<context_summary>` 消息插入到消息列表头部

**建议**：面试官可能追问"为什么用字符数而非 token 数"——回答：真实 tokenizer 有开销，字符数作为启发式误差约 20-30%，但 60000 阈值远低于模型真实窗口，留足安全余量。

---

### Q19: 保留最近 6 条消息够吗？为什么不是 3 条或 10 条？

**答案**：
6 条覆盖了 ReAct 循环的最小完整上下文：
- 1 条用户输入
- 2-3 轮工具调用（每轮 = LLM 回复 + 工具结果 = 2 条）

太少（3 条）：可能丢失最近的工具执行结果，LLM 不知道上一步做了什么 → 重复操作
太多（10 条）：压缩效果差，上下文仍然很长

**建议**：这个数字的选择要能解释"最小完整上下文"的概念。

---

## 七、工程设计（追问题）

### Q20: 项目用了哪些设计模式？为什么选这些？

**答案**：
| 模式 | 位置 | 解决什么问题 |
|------|------|-------------|
| ReAct Loop | agent_loop.py | Agent 自主决策循环 |
| Facade | executor.py | 隐藏沙箱实现，预留替换入口 |
| Dispatch Map | registry.py | O(1) 工具路由，开放封闭 |
| 依赖注入 | main.py | 组件解耦，可测试 |
| Strategy | retry_strategy.py | 可替换的重试策略 |
| DataClass | Action, ExecutionResult | 类型安全的数据传递 |
| Module Singleton | 各 builtin 工具 | 简化工具函数签名 |
| Composition Root | main.py | 集中管理依赖图 |

**建议**：不需要全部说，挑 3-4 个重点的（Facade、Dispatch Map、Strategy）讲清楚 why。

---

### Q21: Dispatch Map 相比 if-elif 有什么优势？

**答案**：
```python
# if-elif 方式（O(n)，新增工具要改路由代码）
if name == "run_code": return run_code(args)
elif name == "read_file": return read_file(args)
elif name == "write_file": return write_file(args)
# 每加一个工具就要改一行...

# Dispatch Map 方式（O(1)，新增工具只需 register）
self._tools = {"run_code": handler1, "read_file": handler2, ...}
return self._tools[name](args)  # O(1) 查找
```

优势：
- **O(1)** vs O(n) 查找
- **开放封闭原则**：新增工具只需 `register()`，不改路由代码
- **运行时动态性**：可以热插拔工具

**建议**：这是经典的设计模式面试题，Dispatch Map = 策略模式的简化版。

---

### Q22: 测试覆盖了哪些场景？有没有遗漏？

**答案**：
20 个单元测试覆盖三大模块：
- **沙箱**（7 项）：基本执行、错误捕获、超时、环境变量隔离
- **自愈**（7 项）：错误分类、修复建议、重试限制、resource 拒绝
- **Agent 核心**（6 项）：上下文管理、工具注册、未知工具降级、Todo 管理

遗漏：
- **集成测试**：没有端到端的 Agent 循环测试（因为依赖真实 LLM）
- **CodeAct 降级**：没有测试正则提取代码块的各种边界情况
- **并发安全**：没有测试多线程/多进程场景

**建议**：诚实说出遗漏，然后说"如果时间允许会补上"。

---

### Q23: 如果让你把这个项目做到生产级别，需要改什么？

**答案**：
1. **沙箱升级**：subprocess → Docker/gVisor，加内核级隔离
2. **并发执行**：支持 parallel tool calls（OpenAI 可以一次返回多个工具调用）
3. **持久化记忆**：加向量数据库，跨会话记住用户偏好和历史
4. **模型管理**：支持多模型切换 + 回退（主模型不可用时自动切换备用模型）
5. **监控告警**：加指标采集（成功率、平均轮次、token 消耗）+ 告警
6. **流式工具结果**：代码执行过程的实时输出（而非等执行完才返回）

**建议**：挑 2-3 个最重要的展开说，不要贪多。
