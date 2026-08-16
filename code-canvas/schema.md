# Code Canvas — JSON schema v0.1

一份 canvas JSON 渲染成一个自包含 HTML。渲染器负责精确布局（测量代码行宽、
排列列与行带、包住区域、计算镜头）；agent 只给**粗位置**和内容。

```jsonc
{
  "meta": {
    "title": "Code Canvas",          // 左上角标题
    "subtitle": "orders 服务 · 写路径" // 标题旁的小字
  },

  "regions": [                        // 故事线区域（着色框）
    {
      "id": "A",
      "title": "故事线 A · 请求主流程", // 标签胶囊
      "blurb": "请求的进与出",          // 标签下一句话，≤20 字，可省略
      "hue": "blue",                  // blue | green | violet | amber
      "cards": ["handler", "fetch"]   // 成员卡片；区域矩形自动包住它们
    }
  ],

  "cards": [
    {
      "id": "handler",
      "name": "handle_request(req)",  // 头部签名
      "file": "server/handler.py",
      "lang": "py",                   // py | js | 其他(退化为普通高亮)
      "layout": { "col": 0, "band": 0 }, // 粗位置：列(0..n 左→右)、行带(0..n 上→下)
      "collapsed": false,             // 默认折叠成签名条？重点卡 false
      "code": "def handle_request(req):\n    ...", // 原文，行号从 1 起
      "blocks": [                     // 可选：长函数的逻辑块（行段树，非 AST）
        {
          "name": "水位检查",          // 块名（色条上）
          "summary": "低于高水位就什么都不做", // 一句话功能，≤20 字
          "lines": [2, 4],            // 闭区间行号
          "folded": true,             // 默认折叠成大纲条
          "children": [ /* 嵌套子块，行段必须落在父块内 */ ]
        }
      ]
    }
  ],

  "wires": [                          // 策展的线：只画对故事重要的
    { "id": "w-key",  "kind": "call", // call=调用/执行(灰) | data=数据流(琥珀)
      "from": { "card": "handler", "line": 2 },        // line 可省 → 卡片边缘
      "to":   { "card": "cachekey" } },                // side 可选 left|right
    { "id": "d-key",  "kind": "data", "label": "key",  // data 线建议带值名
      "from": { "card": "cachekey", "line": 5 },
      "to":   { "card": "get" } }
  ],

  "notes": [
    { "id": "bg0", "flavor": "bg",      // bg=背景(青) | intent=意图/不变量(琥珀)
      "tag": "背景 · 这是什么",
      "text": "……",                     // bg 画布级 ≤80 字；概念 ≤60 字；intent ≤60 字
      "place": { "corner": "nw" },      // 画布级背景卡：西北角
      "step": 0 },                      // 在哪一步点亮（0=总览）
    { "id": "n1", "flavor": "intent",
      "tag": "NOTE · handler.py:6",
      "text": "……",
      "anchor": { "card": "handler", "line": 6 },  // 引线锚到具体行
      "place": { "side": "left", "of": "handler" },// 摆放：卡片左/上 (left|above)
      "step": 2 }
  ],

  "steps": [                          // 故事线镜头路径；第 0 步通常是总览
    { "title": "总览", "caption": "……", "fit": true },
    { "title": "① 请求如何变成 key",
      "caption": "……",                 // ≤80 字
      "wires": ["w-key", "d-key"],    // 本步点亮的线；其余淡出
      "lines": [["handler", 2]],      // 本步高亮的行
      "expand": ["cachekey"],         // 本步自动展开的卡
      "focus": ["handler", "cachekey", "n3"] } // 取景元素（卡/note id）；镜头自动计算
  ]
}
```

## 渲染器行为（约定）

- **布局**：列 x 由该列最宽卡片决定（列间距固定）；带 y = 带号 × 带高，
  同列冲突自动下推。区域矩形 = 成员卡片 bbox + padding，实时跟随展开/折叠。
- **锚点级联**：线/引线锚到行；行被折叠时退到所在块的大纲条；卡片折叠时退到卡片边缘。
- **块颜色**：渲染器按层深自动从两套色板分配，agent 不指定颜色。
- **镜头**：`focus` 元素的 bbox 决定中心与缩放；`fit` 取全图。
- **交互**：拖拽平移、滚轮缩放、点卡头折叠/展开、点块条折叠/展开、
  ◀▶/←→ 步进、`#s2` 直达步骤（尾缀 `x` = 全展开，调试用）。

## 硬约束（agent 侧，渲染器不校验但 review 时执行）

- 每步点亮的线 ≤ 5，邻域卡片 ≤ 4，行高亮 ≤ 6
- 每卡 intent note ≤ 3；文字上限见字段注释，写不下说明还没想清楚
- 代码行 ≤ 60 字符（更长的行考虑换行重排或截选）
- 块必须是"一句话说得清功能"的行段；不做 AST 粒度
- data 线只画故事需要的"值的旅程"；call 线是骨架但同样只画在场的
