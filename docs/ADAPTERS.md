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
- 自动 input count 控制
- 多媒体统一聚合成 URL 数组
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
- `maxInputNum`
  - 多输入媒体的最大数量。只要媒体参数的 `maxInputNum > 1`，运行时就会把它当作多输入媒体，并生成对应的额外输入口与自动 `inputcount`
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

hook 函数统一使用：

```python
def my_hook(value, context):
    ...
```

`context` 是 `HookContext`，通过具名属性和方法暴露当前参数、节点输入、媒体输入和已解析 model，避免继续传递含义不直观的多位置参数。

## 6. 复杂节点如何落到通用规则

### Wan 2.7 Image

主要依赖：

- 扁平化后的固定 `model_name`
- 自动 `image_inputcount`
- `valueHook: wan.custom_size`
- `valueHook: wan.bbox_list`
- `valueHook: wan.color_palette`
- `sendIf`

### Wan 2.7 Video Edit

主要依赖：

- 多个语义不同的媒体参数分别使用自己的 list 字段
- 后端 template 决定如何把这些 list 字段转换成真正的后端请求结构

### Seedance 2.0 Multimodal

主要依赖：

- 固定 `model_name`
- 三组媒体参数的自动 input count
- 自动聚合成 `imageUrls` / `videoUrls` / `audioUrls`

## 7. 媒体字段约定

当前前端节点层已经统一成下面的规则：

- 只要是媒体参数，最终写进 payload 时一律是 URL list
- 即使只有一个媒体输入，也发送单元素 list
- 只要 `maxInputNum > 1`，就视为多输入媒体；不再需要 `multipleInputs`
- 不再支持 `flattenBatches`
- 不再支持 `forceList`
- 不再支持 `mediaItemType`

也就是说，前端节点层只负责：

- 采集媒体输入
- 上传得到 URL
- 按 `fieldKey` 写成 URL list

如果后端需要把多个媒体字段进一步转换成某种 template 结构，应当由后端 template 负责，而不是前端 registry 负责。

## 8. 新增节点建议

优先顺序：

1. 先只写基础字段和 `params`
2. 再补少量声明式元数据
3. 如果仍然不够，再新增有限 hook

不要再为单个模型写一份专属 adapter。
