# Models Registry Guide

这份文档描述当前仓库里 [`models_registry.json`](/Users/huhuhu/Desktop/refactor/bizytrd/models_registry.json) 的实际 schema。

核心原则只有三条：

1. `category` 只用于 ComfyUI 菜单展示
2. endpoint 由 `model_name` 和 `endpoint_category` 组装（channel参数会影响model_name）
3. registry 不再写 `transform` 这类动作逻辑，只允许引用少量预定义 hook

对应实现：

- [`nodes/node_factory.py`](/Users/huhuhu/Desktop/refactor/bizytrd/nodes/node_factory.py)
- [`core/base.py`](/Users/huhuhu/Desktop/refactor/bizytrd/core/base.py)
- [`core/adapters.py`](/Users/huhuhu/Desktop/refactor/bizytrd/core/adapters.py)

## 1. 最小结构

```json
{
  "internal_name": "BizyTRD_Example",
  "class_name": "BizyTRDExample",
  "display_name": "BizyTRD Example",
  "category": "BizyTRD/Example",
  "model_name": "nano-banana-pro",
  "endpoint_category": "Text To Image",
  "output_type": "image",
  "params": [
    {
      "name": "prompt",
      "fieldKey": "prompt",
      "type": "STRING",
      "required": true
    }
  ]
}
```

运行时 endpoint 会组装成：

```text
nano-banana-pro/text-to-image
```

## 2. 模型级字段

### 必填字段

- `internal_name`
  - 节点 class mapping 的键
- `class_name`
  - 运行时生成的 Python 类名
- `display_name`
  - 节点显示名称
- `category`
  - ComfyUI 菜单分类
- `output_type`
  - `image`、`video`、`audio`、`string`
- `params`
  - 输入参数定义

### endpoint 相关字段

- `model_name`
  - endpoint 前半段的基础模型名
- `endpoint_category`
  - endpoint 后半段，运行时转成小写并把空格替换为 `-`

示例：

```json
"model_name": "nano-banana-pro",
"endpoint_category": "Image To Image"
```

最终 endpoint：

```text
nano-banana-pro/image-to-image
```

### 渠道相关约定

不再支持模型级渠道元数据。

如果某个模型需要渠道切换，只允许定义一个固定名字的输入参数：

- `channel`

运行时规则：

- `channel` 为空时，不修改 `model_name`
- `channel` 非空时，直接把 `channel` 规范化后追加到 `model_name` 后面
- 规范化规则是：去首尾空格、转小写、空白转 `-`、`_` 转 `-`

例如用户传入：

```text
channel = Official API
```

则 endpoint 前半段会变成：

```text
nano-banana-pro-official-api
```

### payload model 相关字段

payload 中的 `model` 与 endpoint 前半段保持一致，也会叠加同样的 `channel` 后缀。

## 3. 参数级字段

### 基础字段

- `name`
- `fieldKey`
- `type`
- `required`
- `default`
- `description`
- `multiline`
- `forceInput`
- `options`
- `min` / `max`

### 输入显示顺序

节点最终显示给用户的输入顺序不再直接依赖 registry 中 `params` 的书写顺序。

当前运行时会做稳定排序：

- 先显示媒体输入，顺序固定为 `IMAGE -> VIDEO -> AUDIO`
- 然后显示 `channel`
- 然后显示普通文本控件，其中 `prompt` / `text` 在前，`negative_prompt` / `negativeprompt` 在后，其余参数最后
- 同一类内部保持 registry 里的相对顺序

这条规则同时作用于 `required` 和 `optional` 输入。

如果某个模型声明了 `channel`，即使它的默认值是空字符串，也仍然会固定显示在媒体输入之后、普通 widget 之前。空值只影响运行时 endpoint 组装，不影响 UI 排序。

## 4. 多输入媒体

适用于 `IMAGE` / `VIDEO` / `AUDIO`。

### 基本写法

```json
{
  "name": "images",
  "fieldKey": "imageUrls",
  "type": "IMAGE",
  "maxInputNum": 4
}
```

会生成：

- `images`
- `image_2`
- `image_3`
- `image_4`
- `image_inputcount`

### 自动 inputcount 规则

当参数满足下面条件时，不需要再手写 count 参数：

- `type` 是媒体类型
- `maxInputNum > 1`
- `name` 是 `image` / `images` / `video` / `videos` / `audio` / `audios`

系统会自动补：

- `image_inputcount`
- `video_inputcount`
- `audio_inputcount`

并且最大数量直接取媒体参数上的 `maxInputNum`。

- `maxInputNum`
  - 正式字段
  - 定义媒体参数允许展开的最大输入数量
  - 只要 `maxInputNum > 1`，运行时就会把它视为多输入媒体
  - 自动生成的 `*_inputcount` 控件当前值只决定“这次实际读取几个输入”
  - 如果没有自动 `*_inputcount` 控件，运行时会直接按 `maxInputNum` 读取全部展开输入

## 5. payload 构建相关字段

- `internal`
  - 输入存在于节点中，也会进入运行时 `kwargs`
  - 但这个字段本身不会直接写进 payload
  - 适合只给 hook 或条件判断使用的辅助参数，例如 `custom_width`、`custom_height`
- `hidden`
  - 输入不会展示在 ComfyUI 节点界面中
  - 字段仍然会按普通 payload 参数处理
  - 如果运行时没有传入同名值，会使用 `default` 作为 payload 值
  - 适合后端需要固定发送、但用户不需要配置的参数，例如 `watermark`
  - 它只是隐藏 UI，不是安全隐藏；值仍然存在于 registry 和 payload 中
- `sendIf`
  - 决定当前字段在什么条件下才发送
  - 它只看“当前字段自己的值”，不看别的字段
  - 当前支持：
    - `non_empty`：非空才发送
    - `true`：值为真才发送
    - `gte_zero`：值大于等于 `0` 才发送
    - `nonzero`：值不等于 `0` 才发送
    - `not_default`：值与 `default` 不同才发送
    - `always`：总是发送
- `skipValues`
  - 一个数组
  - 如果当前值命中数组中的任意元素，则不发送
  - 适合处理后端定义的显式哨兵值，例如 `["", "auto"]`
- `onlyIfTrueParam`
  - 只有当另一个参数为真时，当前字段才发送
  - 这里引用的是“另一个参数的 `name`”
- `onlyIfFalseParam`
  - 只有当另一个参数为假时，当前字段才发送
  - 这里引用的是“另一个参数的 `name`”
- `onlyIfMediaAbsent`
  - 只有当指定媒体参数当前没有任何输入时，当前字段才发送
  - 判断依据是该媒体参数收集后的实际数量
- `onlyIfMediaPresent`
  - 只有当指定媒体参数当前至少有一个输入时，当前字段才发送
  - 判断依据是该媒体参数收集后的实际数量

这些字段的执行顺序是：

1. 先取原始输入值；`hidden: true` 且运行时没有传值时，取 `default`
2. 如果有 `valueHook`，先做值转换
3. 再判断 `skipValues`
4. 再判断 `onlyIf*`
5. 最后判断 `sendIf`

只有全部通过后，这个字段才会进入最终 payload。

### 媒体 payload 约定

当前主 registry 已经统一成下面的前端媒体规则：

- 只要是媒体参数，最终写进 payload 时一律是 URL list
- 即使只有一个媒体输入，也发送单元素 list
- 只要 `maxInputNum > 1`，运行时就把它视为多输入媒体
- 不再支持 `multipleInputs`
- 不再支持 `flattenBatches`
- 不再支持 `forceList`
- 不再支持 `mediaItemType`

前端节点层不再把多个媒体参数组装成 typed media object array。

如果后端需要把多个 list 字段进一步转换成 template 结构，应当由后端 template 负责。

## 6. Hook 字段

不再使用 `transform`。

如果需要有限的值转换，使用：

- `valueHook`

当前内建 hook：

- `common.json_loads`
- `wan.custom_size`
- `wan.bbox_list`
- `wan.color_palette`

这些 hook 已经按 provider / 领域拆到 [`core/hooks`](/Users/huhuhu/Desktop/refactor/bizytrd/core/hooks) 下。

`valueHook` 现在必须使用脚本路径格式：

```json
"valueHook": "wan.custom_size"
```

不再通过 registry 传 `hook*Param` 这类辅助字段。hook 函数统一使用简洁签名：

```python
def my_hook(value, context):
    ...
```

`value` 是当前参数的原始输入值。`context` 是 `HookContext`，提供清晰命名的上下文：

- `context.param`：当前参数定义
- `context.inputs`：当前节点全部输入
- `context.media`：已归一化的媒体输入信息
- `context.resolved_model`：已解析的 payload model
- `context.get(name, default=None)`：读取某个节点输入
- `context.get_media(name, default=None)`：读取某个媒体参数的完整归一化信息

provider-specific hook 可以通过 `context.get()` 和 `context.get_media()` 读取当前节点约定字段。

例如：

```json
{
  "name": "size",
  "fieldKey": "size",
  "type": "LIST",
  "valueHook": "wan.custom_size"
}
```

## 7. 手写配置节点与消费方式

少数本地 helper/config 节点不放进 registry 生成链路。它们显式注册在：

- [`nodes/manual`](/Users/huhuhu/Desktop/refactor/bizytrd/nodes/manual)

当前手写配置节点包括：

- `BizyTRD_DoubaoToolConfig`
- `BizyTRD_MultiPromptConfig`
- `BizyTRD_LLMToolConfig`

使用这些配置节点的普通 registry 节点仍然只需要声明一个普通参数。推荐写法是：

```json
{
  "name": "tools",
  "fieldKey": "tools",
  "type": "STRING",
  "required": false,
  "default": "[]",
  "forceInput": true,
  "valueHook": "common.json_loads"
}
```

约定：

- `forceInput: true` 让 ComfyUI 把这个字段显示成可连接输入口，而不是普通文本 widget
- `common.json_loads` 会把 JSON 字符串配置转成 list/dict
- 如果上游配置节点已经返回 list/dict，`common.json_loads` 会直接透传
- 不需要给 registry 增加新的节点类型字段；特殊节点只在 `nodes/manual` 手写并注册

例如 `MultiPromptConfig` 输出 JSON 字符串，消费节点使用 `valueHook: common.json_loads` 后，payload 中的 `multi_prompt` 会是 list。

例如 `DoubaoToolConfig` 输出 `["web_search"]`，消费节点也可以使用同一个 hook，payload 中的 `tools` 会保持 list。

## 8. 推荐模式

### 最简单节点

```json
{
  "internal_name": "BizyTRD_SimpleTextToImage",
  "class_name": "BizyTRDSimpleTextToImage",
  "display_name": "BizyTRD Simple Text To Image",
  "category": "BizyTRD/Test",
  "model_name": "simple-model",
  "endpoint_category": "Text To Image",
  "output_type": "image",
  "params": [
    {
      "name": "prompt",
      "fieldKey": "prompt",
      "type": "STRING",
      "required": true,
      "multiline": true
    }
  ]
}
```

### 多图输入

```json
{
  "name": "images",
  "fieldKey": "imageUrls",
  "type": "IMAGE",
  "maxInputNum": 4
}
```

### 有限 hook

```json
{
  "name": "payload_json",
  "fieldKey": "payload_json",
  "type": "STRING",
  "valueHook": "common.json_loads"
}
```

### 媒体参数统一发送 list

```json
{
  "name": "images",
  "fieldKey": "imageUrls",
  "type": "IMAGE",
  "maxInputNum": 4
}
```

运行时即使只输入 1 张图片，也会发送：

```json
{
  "imageUrls": ["https://..."]
}
```

## 9. 不建议再做的事

- 不要再在 registry 里写 `transform`
- 不要再手写默认的 `image_inputcount` / `video_inputcount` / `audio_inputcount`
- 不要把 UI 展示字段和 endpoint 路由字段混在一起
- 不要再使用 `multipleInputs`
- 不要再使用 `flattenBatches` / `forceList` / `mediaItemType`
- 不要为单个模型新增专属 adapter，优先扩展统一 builder 或有限 hook
