---
name: code-canvas
description: Turns code reading or diff review into an interactive 2D canvas instead of a linear document. Produces a self-contained HTML canvas of function-level code cards laid out spatially, with typed wires (call vs data flow) anchored to specific lines, line-attached intent notes, teal background notes, colored storyline regions, and a step-by-step guided camera. Long functions render as a fold-out outline of named logical blocks. Use when the user wants to understand a codebase, walk through code, or review changes visually — triggers include "walk me through", "explain this code", "how does X work", "make a canvas/walkthrough of", or dissatisfaction with reading long diffs top-to-bottom.
---

# code-canvas skill (v0.1)

代码是源码，图是投影。本 skill 读一段代码（或一个变更），产出一张
**可平移缩放的 2D 画布**：函数级代码卡片 + 策展过的连线 + 行级注释 +
故事线镜头。设计决定见 `DESIGN.md`，数据格式见 `schema.md`。

## 管线

0. **确认读者画像**：问（或从对话中提取）这张图为谁生成——经验水平、
   关注点、语言、讲法偏好。写进 `meta.audience`，所有文字字段按它来写。
   用户没说就用默认："有经验的工程师；中文；准确优先"。
   注意：这只是默认视角——读者还能在页面上设置自己的画像，对说明和
   变元注释做运行时的「按我的画像重讲」（见 schema.md）
1. **确定范围**（同旧 skill 的 Mode A/B：给了文件直接读；给了主题先提
   scope 提案，用户确认后继续）
2. **读全文**，识别故事线（region）与卡片（函数/方法级）
3. **策展连线**：call 线是骨架（call site 行 → 被调卡片）；data 线只画
   故事需要的"值的旅程"（值产生行 → 消费卡片，带值名 label）
4. **分层细节**：重点卡 `collapsed:false` + 行级 note；次要卡折叠。
   长函数（约 15 行以上或嵌套深）写 `blocks` 行段树——按"一句话说得清
   功能"分段，不按 AST；嵌套结构套 children。值得多讲两句的块加
   `explain`（≤120 字，回答"为什么这么写/坑在哪"，不复述代码）。
   不好懂的标识符加 `terms` 变元注释（≤60 字，回答"这个变量装的是什么"）
5. **背景三层**：画布级 bg note（corner nw，step 0 点亮）、region blurb、
   概念级 bg note（锚到行，在相关 step 点亮）。字数硬上限见 schema.md
6. **写 steps**：第 0 步总览（fit），后续每步 = 点亮的线 + 高亮的行 +
   focus 取景元素 + ≤80 字 caption。步子按"读者的问题"排，不按文件序
7. **产出 JSON，先过验证器再渲染**（不可跳过）：

   ```bash
   python3 validate.py canvas.json   # ERROR 必须清零；warn 逐条自查
   python3 render.py canvas.json output.html
   ```

   验证器抓机械错误（悬空引用、行号越界、块区间重叠、token 不在行上）
   和预算超限（每步线数/行数、各类文字上限）。ERROR 不清零的图是坏的。

8. **截图自检**（有 headless chromium 时，逐项过下面的清单）：
   总览 + 每个 step 各截一张；`#s2` 直达步骤，调试尾缀 `x` 全展开、
   `e` 开说明、`t` 开变元注释、`q` 开问答抽屉
9. **（可选）开启块级问答**：`python3 serve.py output.html --repo <仓库路径>`，
   从 localhost 打开——每个块的「问」变成真问答（桥接 `claude -p`）。
   静态打开时「问」降级为复制上下文提问到剪贴板

## Diff 画布（第三种画布类型）

输入是一个 diff / PR 时（`meta.mode: "diff"`，参考 `demo/cache-diff.json`）：

- 卡片 = 被改动的函数的 **head 全文** + `diff` 标记（added 行绿、removed
  原文红删除线）；未改动但受影响的邻居做上下文卡（折叠）
- 故事线 = **变更意图**（"本次变更" + "未改动的邻居"是最小形态），不按文件分
- step 顺序 = 评审者的问题序列：**这个 PR 治什么病 → 核心改动（逐个）→
  连锁影响 → 回归风险**。风险步是必选项——没有风险判断的 diff 画布只是
  上色的 diff
- removed 只放读懂变更所必需的原文，不搬运整个旧版本

### 摄入管线（从真实 diff 到 card.diff，行号必须机械算）

1. 定基与头：`BASE=<sha>^`、`HEAD=<sha>`（PR 则是 merge-base 与分支头）
2. `git show --stat HEAD` 圈出改动文件；逐文件决定哪些函数开卡
3. 每张卡：从 HEAD 版文件取函数原文（记下起始行），然后**用 diff_map.py
   算 diff 字段，不要手工对**：
   ```bash
   git show BASE:path/to/file.py > /tmp/base.py
   git show HEAD:path/to/file.py > /tmp/head.py
   python3 diff_map.py /tmp/base.py /tmp/head.py --head-start <函数起始行> --head-count <行数>
   ```
   输出即卡片的 `diff` 字段（卡内相对行号已换算好）
4. 纯新增函数：`added` 覆盖全部行；被整段删除的函数：并入邻居卡的
   removed 或开"已删除"说明 note，不为死代码单独开卡

### 评审发现（findings）

评审意见写成带 `severity` 的 intent note：`blocker`（不改不能合）/
`concern`（应当处理）/ `nit`（顺手改）。渲染器自动出左上角发现计数器，
点击逐个跳转。规范：每条发现锚到具体行；风险步的 focus 必须包含全部
blocker/concern；没有任何发现的评审要在末步 caption 明说"没有拦截意见"
——沉默不是结论。

## 规模闸门：大仓库先领航，后深潜

动笔前先估计**这张图要讲的东西**的代码量（不是仓库总行数）：

- **≤ ~2000 行**（一个模块 / 明确主题的切片）→ 直接出细粒度画布
  （函数级卡片 + 完整故事线，`demo/nano-vllm.json` 的形态）
- **更大，或用户就说"给我讲讲这个仓库"** → 先出**领航图**：
  - 卡片 = 子系统/模块（≤9 张）。卡内放"名片代码"：该子系统入口函数或
    核心类型定义的**原文连续摘选**（≤12 行），`file` 字段标 `路径:起始行`
  - 线 = 子系统间的调用/数据关系，每种关系一根代表线，不穷举
  - 故事线 = 架构关切（主流程 / 安全边界 / 状态与存储…），2-3 条
  - 块和变元注释从简；bg note 讲清"这个仓库是什么、怎么分层"
  - **最后一步的 caption 列出 3-5 个值得深潜的主题**，邀请用户挑
  - 用户挑了主题 → 按细粒度管线另出一张深潜画布（一个主题一张）

## 布局：agent 只给粗位置

每张卡片给 `layout: {col, band}`——列（0 起，左→右，按调用方向排）与
行带（0 起，上→下）。渲染器测量代码行宽定列宽、自动下推解决同列冲突、
用成员卡片 bbox 实时包住 region、根据 focus 列表自动计算镜头。
**不要**试图给像素坐标。

经验规则：入口函数 col 0；被调的下一层 col+1；同一 region 的卡尽量占
连续的列；一列不超过 3 张卡。

## 硬约束（写 JSON 时自查）

- 每步：线 ≤ 5、focus 里的卡 ≤ 4、高亮行 ≤ 6
- 每卡 intent note ≤ 3；bg 画布级 ≤80 字、blurb ≤20 字、概念 note ≤60 字
- **行宽**：目标 ≤90 字符，>100 会触发 validate 警告。允许对超宽行做
  **保持 token 顺序的换行重排**（注释续行补 `//`），须在交付报告中披露；
  除此之外卡片代码 = 原文，不改写、不省略中段
- **长函数可拆多卡**：连续摘选 + `file` 标 `路径:起始行`（此格式适用于
  一切卡片，不限领航图），卡名可带 ①②
- **行号锚点用脚本算，不要手数**：块区间 / 线锚 / term 行号 / step 高亮
  一律在最终卡文上按子串搜索程序化计算（尤其做过换行重排时）
- 块必须能用一句话说清功能；深嵌套才用 children，不为分块而分块
- 不确定的意图不写进 note——note 是断言，不是猜测

## 布局与摆位的渲染器现实（评测实测出的规则）

- **宽度预算**：≥6 列的画布总览会小到难读，**≤5 列封顶**；行宽收窄可救列宽
- 左置 note 指向非 0 列的卡时，该列前会加一条 ~320px 的 note 车道（加宽画布）
- note **每次重绘跟随目标卡**：above 位被上方展开的卡挤压时自动下滑，
  实在没空间会退化成挂在目标卡左侧；同一张卡多条 `above` 仍会原地重叠，避免
- 步骤状态是**累积**的（`expand`/`unfold` 只加不减）：直达 `#s5` 和顺序走到
  第 5 步画面不同；截图自检以顺序走为准
- 调试尾缀 `q` 依赖块条的「问」按钮，无 blocks 的画布上无效果

## 截图自检清单

每张截图对照检查，任何一条不过就改 JSON 重渲染：

- [ ] 没有元素互相压盖（note 压卡、卡压卡、note 压区域标签）
- [ ] 每步的 focus 镜头框住了 caption 里提到的所有东西（尤其行注释）
- [ ] 点亮的线两端都可见，line 锚点落在正确的行上
- [ ] 折叠卡的大纲（块色条）在总览缩放下可读
- [ ] 每张卡至少被一个 step 聚焦过；没有 step 聚焦不存在的重点
- [ ] caption 说"注意 X"时，X 确实在画面里且处于点亮态

## 失败模式

- **大仓库直接细讲**：在十万行仓库上硬出函数级画布 = 随机切片，读者不知道
  自己在整体的哪里。先领航图，后深潜
- **全量连线**：把静态分析能找到的边都画上 = 毛线球。线是叙事的一部分
- **AST 粒度分块**：每个 for/if 都成块 = Blueprint 噪音。逻辑粒度才对
- **背景膨胀**：背景写成段落 = 退回线性文档。写不进上限说明没想清楚
- **step 即文件序**：步子要回答读者的问题（怎么进、怎么出、坏了会怎样），
  不是按文件逐个介绍
- **卡片改写代码**：卡内必须是原文。信任建立在"我看到了真实的行"上

## 文件

- `SKILL.md` — 本文件
- `DESIGN.md` — 设计决定与理由
- `schema.md` — canvas JSON 格式
- `template/canvas.html` — 数据驱动的单文件渲染模板（布局引擎在里面）
- `validate.py` — canvas JSON 验证器：机械错误 + 预算超限（渲染前必过）
- `diff_map.py` — base/head 两文件 + 卡片行段 → 机械算出 card.diff
- `render.py` — JSON → HTML 注入脚本
- `serve.py` — 块级问答服务：serve HTML + `/ask` 桥接 claude/codex CLI
- `tests/` — Playwright 交互回归 + 个性化端到端测试
- `demo/cache-demo.json` / `.html` — 参考示例（缓存中间件，4 步故事线）
- `mock/canvas-mock-v1.html` — 手工排版的形态原型（历史参考，勿再改）

## 与旧 skill 的关系

取代 `code-review-skill` 与 `code-reading-walkthrough` 的线性 HTML 文档
形态。旧 skill 的分析管线思想（storyline 策展、重要性取舍、意图注释）
保留，表达层全部换成本 canvas。
