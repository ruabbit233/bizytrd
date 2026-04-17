# Payload Builder

[`core/adapters.py`](/Users/huhuhu/Desktop/refactor/bizytrd/core/adapters.py) 现在负责两件事：

- 把 registry 定义转换成请求 payload
- 尽量把特殊行为限制在少量预定义 hook，而不是在 registry 里写动作逻辑

## 1. 当前设计

整体目标是贴近 `ComfyUI_RH_OpenAPI`：

- 节点定义由 registry 驱动
- payload 构建由统一 builder 完成
- registry 只表达数据，不承载任意动作逻辑

## 2. builder 当前支持的通用能力

- 普通参数按 `fieldKey` 写入 payload
- 媒体参数自动上传
- `multipleInputs`
- 自动或显式的 input count 控制
- 图片批量输入展开 `flattenBatches`
- 多媒体直接聚合成 URL 数组
- 多个媒体参数按 `mediaItemType` 聚合成对象数组
- 简单发送条件：
  - `sendIf: non_empty`
  - `sendIf: true`
  - `sendIf: gte_zero`
  - `sendIf: nonzero`
  - `sendIf: not_default`
- 简单条件依赖：
  - `onlyIfTrueParam`
  - `onlyIfFalseParam`
  - `onlyIfMediaAbsent`
  - `onlyIfMediaPresent`

## 3. 模型级元数据

- `model_name`
  - endpoint 组装时使用的基础模型名
- `endpoint_category`
  - endpoint 后半段，运行时会规范化为小写并把空格转成 `-`

渠道切换不再使用模型级元数据。

如果节点声明了固定参数名 `channel`，builder 会直接读取这个输入，并把规范化后的值追加到 `model_name` 后面。规范化规则是：

- 去首尾空格
- 转小写
- 空白转 `-`
- `_` 转 `-`

## 4. 参数级元数据

- `internal`
  - 节点输入存在，但不直接发给后端
- `multipleInputs`
  - 多输入媒体
- `maxInputNum`
  - 多输入媒体的最大数量
- `inputcountParam`
  - 可选，显式指定 count 参数名；没有时，`images` / `image` / `videos` / `video` / `audios` / `audio` 会自动生成 `<base>_inputcount`
- `flattenBatches`
  - 图片输入按 batch 展开
- `mediaItemType`
  - 把媒体拼成对象数组项
- `sendIf`
- `onlyIfTrueParam`
- `onlyIfFalseParam`
- `onlyIfMediaAbsent`
- `onlyIfMediaPresent`
- `valueHook`
  - 参数值写入 payload 前，命中预定义 hook 做有限转换

## 5. 有限 hook 机制

不再使用 `transform` 这类 registry 动作逻辑。

现在的 hook 体系是“脚本路径 hook”：

- registry 里只写 `valueHook`
- 格式必须是 `<module>.<function>`
- 运行时会从 [`core/hooks`](/Users/huhuhu/Desktop/refactor/bizytrd/core/hooks) 下加载对应函数
- 不允许 `eval`、任意表达式或任意模块执行

当前内建：

- `common.json_loads`
- `wan.custom_size`
- `wan.bbox_list`
- `wan.color_palette`

如果后面确实需要新能力，应当：

1. 先在 [`core/hooks`](/Users/huhuhu/Desktop/refactor/bizytrd/core/hooks) 下新增模块或函数
2. 再在 registry 里引用路径形式的 hook 名

不要把任意表达式或迷你 DSL 放回 registry。

当前 [`core/adapters.py`](/Users/huhuhu/Desktop/refactor/bizytrd/core/adapters.py) 只负责 hook 调度，不再承载 provider 专属 hook 细节。

## 6. 复杂节点如何落到通用规则

### Wan 2.7 Image

主要依赖：

- 扁平化后的固定 `model_name`
- 自动 `image_inputcount`
- `flattenBatches`
- `valueHook: wan.custom_size`
- `valueHook: wan.bbox_list`
- `valueHook: wan.color_palette`
- `sendIf`

### Wan 2.7 Video Edit

主要依赖：

- 多个媒体参数共享 `fieldKey = media`
- 每个媒体参数声明自己的 `mediaItemType`

### Seedance 2.0 Multimodal

主要依赖：

- 固定 `model_name`
- 三组媒体参数的自动 input count
- 自动聚合成 `imageUrls` / `videoUrls` / `audioUrls`

## 7. 新增节点建议

优先顺序：

1. 先只写基础字段和 `params`
2. 再补少量声明式元数据
3. 如果仍然不够，再新增有限 hook

不要再为单个模型写一份专属 adapter。
