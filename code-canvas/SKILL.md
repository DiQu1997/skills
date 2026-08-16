---
name: code-canvas
description: Turns code reading or diff review into an interactive 2D canvas instead of a linear document. Produces a self-contained HTML canvas of function-level code cards laid out spatially, with typed wires (call vs data flow) anchored to specific lines, line-attached intent notes, teal background notes, colored storyline regions, and a step-by-step guided camera. Long functions render as a fold-out outline of named logical blocks. Use when the user wants to understand a codebase, walk through code, or review changes visually — triggers include "walk me through", "explain this code", "how does X work", "make a canvas/walkthrough of", or dissatisfaction with reading long diffs top-to-bottom.
---

# code-canvas skill (v0.1)

代码是源码，图是投影。本 skill 读一段代码（或一个变更），产出一张
**可平移缩放的 2D 画布**：函数级代码卡片 + 策展过的连线 + 行级注释 +
故事线镜头。设计决定见 `DESIGN.md`，数据格式见 `schema.md`。

## 管线

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
7. **产出 JSON**，渲染：

   ```bash
   python3 render.py canvas.json output.html
   ```

8. **验证**（有 headless chromium 时）：截图总览和每个 step，检查
   压盖 / 溢出 / 越界；`#s2` 直达步骤，调试尾缀 `x` 全展开、`e` 开说明、
   `t` 开变元注释、`q` 开问答抽屉
9. **（可选）开启块级问答**：`python3 serve.py output.html --repo <仓库路径>`，
   从 localhost 打开——每个块的「问」变成真问答（桥接 `claude -p`）。
   静态打开时「问」降级为复制上下文提问到剪贴板

## 布局：agent 只给粗位置

每张卡片给 `layout: {col, band}`——列（0 起，左→右，按调用方向排）与
行带（0 起，上→下）。渲染器测量代码行宽定列宽、自动下推解决同列冲突、
用成员卡片 bbox 实时包住 region、根据 focus 列表自动计算镜头。
**不要**试图给像素坐标。

经验规则：入口函数 col 0；被调的下一层 col+1；同一 region 的卡尽量占
连续的列；一列不超过 3 张卡。

## 硬约束（写 JSON 时自查）

- 每步：线 ≤ 5、邻域卡 ≤ 4、高亮行 ≤ 6
- 每卡 intent note ≤ 3；bg 画布级 ≤80 字、blurb ≤20 字、概念 note ≤60 字
- 代码行 ≤ 60 字符；卡片代码 = 原文，不改写不省略中段
- 块必须能用一句话说清功能；深嵌套才用 children，不为分块而分块
- 不确定的意图不写进 note——note 是断言，不是猜测

## 失败模式

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
- `render.py` — JSON → HTML 注入脚本
- `serve.py` — 块级问答服务：serve HTML + `/ask` 桥接 claude/codex CLI
- `demo/cache-demo.json` / `.html` — 参考示例（缓存中间件，4 步故事线）
- `mock/canvas-mock-v1.html` — 手工排版的形态原型（历史参考，勿再改）

## 与旧 skill 的关系

取代 `code-review-skill` 与 `code-reading-walkthrough` 的线性 HTML 文档
形态。旧 skill 的分析管线思想（storyline 策展、重要性取舍、意图注释）
保留，表达层全部换成本 canvas。
