# Models Registry Guide

这份文档描述当前仓库里 [`models_registry.json`](/Users/huhuhu/Desktop/refactor/bizytrd/models_registry.json) 的实际写法和字段语义。

目标是两件事：

1. 让新增节点时尽量只改 registry
2. 明确哪些字段只是 UI/节点定义，哪些字段会影响最终 payload

文档内容以当前代码实现为准，主要对应：

- [`nodes/node_factory.py`](/Users/huhuhu/Desktop/refactor/bizytrd/nodes/node_factory.py)
- [`core/adapters.py`](/Users/huhuhu/Desktop/refactor/bizytrd/core/adapters.py)

## 1. 整体结构

`models_registry.json` 是一个数组，每一项代表一个模型节点定义。

最小结构示例：

```json
{
  "internal_name": "BizyTRD_Example",
  "class_name": "BizyTRDExample",
  "display_name": "BizyTRD Example",
  "category": "BizyTRD/Example",
  "model_key": "example-model",
  "output_type": "image",
  "params": [
    {
      "name": "prompt",
      "api_field": "prompt",
      "type": "STRING",
      "required": true
    }
  ]
}
```

运行链路是：

1. `node_factory` 读取 registry，生成 ComfyUI 节点输入定义
2. 节点执行时，`core/adapters.py` 读取同一份 registry 构建 payload
3. payload 提交给 BizyAir 后端

所以 registry 同时承担两类职责：

- 节点输入 schema
- payload 构建元数据

## 2. 模型级字段

### 必填字段

#### `internal_name`

- 类型：`STRING`
- 用途：节点 class mapping 的键
- 要求：整个 registry 内唯一

示例：

```json
"internal_name": "BizyTRD_Wan27Image"
```

#### `class_name`

- 类型：`STRING`
- 用途：运行时生成的 Python 类名
- 要求：推荐唯一，使用合法类名风格

#### `display_name`

- 类型：`STRING`
- 用途：节点显示名称

#### `category`

- 类型：`STRING`
- 用途：ComfyUI 节点分类

示例：

```json
"category": "BizyTRD/Wan"
```

#### `model_key`

- 类型：`STRING`
- 用途：默认写入 payload 的 `model`
- 说明：如果没有额外配置，payload 会自动带：

```json
{"model": "<model_key>"}
```

#### `output_type`

- 类型：`STRING`
- 支持值：`image`、`video`、`audio`、`string`
- 用途：决定节点返回类型

#### `params`

- 类型：`ARRAY`
- 用途：定义节点的输入参数

### 可选字段

#### `display_name_zh`

- 类型：`STRING`
- 用途：中文展示名
- 说明：当前主要是文档/元数据用途，不直接参与 node factory 逻辑

#### `request_model`

- 类型：`STRING`
- 用途：固定覆盖 payload 中的 `model`
- 适用场景：UI 上显示的是一个模型节点，但请求里要传另一个固定的 model 值

示例：

```json
"model_key": "seedance-2-0-std",
"request_model": "multimodal-to-video"
```

最终 payload 中的 `model` 会是 `multimodal-to-video`。

#### `request_model_from`

- 类型：`STRING`
- 用途：从某个参数值取 payload 中的 `model`
- 适用场景：节点里有一个 `model` 下拉框，最终请求的 `model` 应该跟着该参数走

示例：

```json
"request_model_from": "model"
```

如果用户在参数 `model` 里选择了 `wan2.7-image-pro`，最终 payload 会写入：

```json
"model": "wan2.7-image-pro"
```

#### `require_any_of`

- 类型：`ARRAY[STRING]`
- 用途：要求其中至少一个输入非空
- 支持两类名字：
  - 普通参数名
  - 媒体参数名

示例：

```json
"require_any_of": ["prompt", "images"]
```

含义是：`prompt` 和 `images` 至少要有一个。

#### `require_any_message`

- 类型：`STRING`
- 用途：`require_any_of` 校验失败时的报错文案

#### `migration_source`

- 类型：`OBJECT`
- 用途：记录迁移来源
- 说明：当前不参与运行逻辑，只是追踪信息

常见结构：

```json
"migration_source": {
  "file": "bizyengine/...",
  "class": "OldNodeClass"
}
```

## 3. `params` 数组

`params` 是最核心的部分。每一项既可能用于：

- 生成 ComfyUI 输入口
- 构建 payload

也可能只用于其中之一。

## 4. 参数级通用字段

### 4.1 基础字段

#### `name`

- 类型：`STRING`
- 必填
- 用途：参数在节点执行时的输入名，也是在 `kwargs` 里的键名

示例：

```json
"name": "prompt"
```

#### `api_field`

- 类型：`STRING`
- 推荐填写
- 用途：最终写入 payload 的字段名

示例：

```json
"name": "generate_audio",
"api_field": "generateAudio"
```

如果省略，则默认使用 `name`。

#### `type`

- 类型：`STRING`
- 必填
- 当前支持：
  - `STRING`
  - `INT`
  - `FLOAT`
  - `BOOLEAN`
  - `LIST`
  - `IMAGE`
  - `VIDEO`
  - `AUDIO`

#### `required`

- 类型：`BOOLEAN`
- 用途：决定该输入在 ComfyUI 中是 required 还是 optional

注意：

- 这是节点输入层面的必填
- 不等于 payload 一定会发送
- 是否发送仍然受 `internal`、`send_if`、`only_if_*` 等字段影响

#### `default`

- 类型：按参数类型变化
- 用途：节点输入默认值

#### `description_zh` / `description`

- 类型：`STRING`
- 用途：作为 tooltip/说明文案来源

#### `tooltip_zh` / `tooltip`

- 类型：`STRING`
- 用途：如果想把 tooltip 和 description 分开，可以单独写

#### `multiline`

- 类型：`BOOLEAN`
- 用途：仅对 `STRING` 生效，控制是否多行输入

#### `options`

- 类型：`ARRAY`
- 用途：`LIST` 类型的可选值列表

示例：

```json
"type": "LIST",
"options": ["720P", "1080P"]
```

#### `min` / `max`

- 类型：数字
- 用途：`INT` / `FLOAT` 的 UI 范围限制

## 5. 只影响节点输入生成的字段

这些字段主要由 [`nodes/node_factory.py`](/Users/huhuhu/Desktop/refactor/bizytrd/nodes/node_factory.py) 使用。

#### `multiple_inputs`

- 类型：`BOOLEAN`
- 用途：把一个媒体参数展开成多个输入口

例如：

```json
"name": "images",
"type": "IMAGE",
"multiple_inputs": true,
"max_inputs": 4
```

会生成：

- `images`
- `image_2`
- `image_3`
- `image_4`

具体名字还会受 `extra_input_pattern` 影响。

#### `multiple`

- 类型：`BOOLEAN`
- 用途：`multiple_inputs` 的兼容写法
- 说明：当前 `node_factory` 和 payload builder 都兼容它

推荐：

- 新写法优先使用 `multiple_inputs`
- 旧数据兼容时才保留 `multiple`

#### `max_inputs`

- 类型：`INT`
- 用途：媒体输入展开的最大数量

#### `extra_input_pattern`

- 类型：`STRING`
- 用途：额外输入口命名规则

示例：

```json
"extra_input_pattern": "image_{index}"
```

则展开输入口为：

- `image_2`
- `image_3`
- ...

如果不写，默认是：

```text
<name>_2
<name>_3
...
```

## 6. 只影响 payload 构建的字段

这些字段主要由 [`core/adapters.py`](/Users/huhuhu/Desktop/refactor/bizytrd/core/adapters.py) 使用。

### 6.1 `internal`

- 类型：`BOOLEAN`
- 用途：参数会出现在节点输入里，但不会直接写入 payload

适合这些场景：

- 仅用于控制其他字段的构建逻辑
- 仅作为中间参数

典型例子：

- `inputcount`
- `image_inputcount`
- `custom_width`
- `custom_height`
- `model`（当真正的 payload model 由 `request_model_from` 处理时）

### 6.2 `send_if`

- 类型：`STRING`
- 用途：控制参数什么时候写入 payload

当前支持值：

#### `non_empty`

- 含义：非空才发送
- 常用于 `STRING`

示例：

```json
"send_if": "non_empty"
```

#### `true`

- 含义：只有值为真时才发送

示例：

```json
"name": "enable_sequential",
"send_if": "true"
```

这样 `false` 时不会把该字段发给后端。

#### `gte_zero`

- 含义：值大于等于 0 才发送
- 常用于 `seed = -1` 表示“不传”

#### `nonzero`

- 含义：值不为 0 才发送
- 常用于 `duration = 0` 表示“跟随后端默认行为”

#### `not_default`

- 含义：当值不等于 `default` 时才发送

示例：

```json
"default": "default",
"send_if": "not_default"
```

#### `always`

- 含义：总是发送
- 说明：通常不必显式写，因为默认就是发送

### 6.3 `skip_values`

- 类型：`ARRAY`
- 用途：如果值命中列表，则不发送

示例：

```json
"skip_values": ["default", "auto"]
```

### 6.4 `only_if_true_param`

- 类型：`STRING`
- 用途：只有另一个布尔参数为 `true` 时才发送当前字段

### 6.5 `only_if_false_param`

- 类型：`STRING`
- 用途：只有另一个布尔参数为 `false` 时才发送当前字段

示例：

```json
"name": "thinking_mode",
"only_if_false_param": "enable_sequential"
```

### 6.6 `only_if_media_absent`

- 类型：`STRING`
- 用途：只有某个媒体参数没有输入时才发送当前字段

示例：

```json
"only_if_media_absent": "images"
```

### 6.7 `only_if_media_present`

- 类型：`STRING`
- 用途：只有某个媒体参数存在输入时才发送当前字段

## 7. 媒体参数相关字段

适用于 `IMAGE` / `VIDEO` / `AUDIO` 参数。

### 7.1 默认行为

如果一个媒体参数没有特殊配置：

- 单输入媒体参数：
  - 会上传
  - payload 写成单个 URL
- 多输入媒体参数：
  - 会收集多个输入
  - 上传后写成 URL 数组

### 7.2 `inputcount_param`

- 类型：`STRING`
- 用途：控制多输入媒体实际读取多少个端口

示例：

```json
"name": "images",
"multiple_inputs": true,
"max_inputs": 9,
"inputcount_param": "inputcount"
```

如果 `inputcount = 3`，则只读取：

- `images`
- `image_2`
- `image_3`

后面的输入口即使存在，也不会参与当前请求。

### 7.3 `flatten_batches`

- 类型：`BOOLEAN`
- 用途：把 batched image tensor 展平为单图列表
- 适用场景：图片输入既可能是一张，也可能是 batch

### 7.4 `force_list`

- 类型：`BOOLEAN`
- 用途：即使不是多输入，也强制把媒体 URL 作为数组写入 payload

### 7.5 `media_item_type`

- 类型：`STRING`
- 用途：把多个媒体参数按对象数组方式聚合到同一个 `api_field`

这是当前实现里一个很重要的能力。

示例：

```json
{
  "name": "video",
  "api_field": "media",
  "type": "VIDEO",
  "media_item_type": "video"
},
{
  "name": "first_frame_image",
  "api_field": "media",
  "type": "IMAGE",
  "media_item_type": "first_frame"
}
```

最终 payload 会生成：

```json
"media": [
  {"type": "video", "url": "..."},
  {"type": "first_frame", "url": "..."}
]
```

这正是 `Wan27VideoEdit` 当前的写法。

### 7.6 上传控制字段

#### `upload_file_name_prefix`

- 类型：`STRING`
- 用途：控制上传文件名前缀
- 支持模板变量：
  - `{index}`
  - `{name}`

示例：

```json
"upload_file_name_prefix": "wan27_image_{index}"
```

#### `upload_total_pixels`

- 类型：`INT`
- 仅适用于图片
- 用途：上传前图片转换的像素上限

#### `upload_max_size`

- 类型：`INT`
- 适用于图片、视频、音频
- 用途：上传文件大小上限，单位字节

#### `upload_format`

- 类型：`STRING`
- 仅适用于音频
- 用途：上传时采用的音频格式

#### `upload_duration_range`

- 类型：`ARRAY[number, number]`
- 仅适用于视频
- 用途：上传前限制视频时长范围

示例：

```json
"upload_duration_range": [2.0, 10.0]
```

## 8. transform 字段

`transform` 用于在参数写入 payload 前做统一转换。

### 8.1 `custom_size`

适用于“UI 上是多个参数，payload 里是一个 size 字段”的场景。

常见搭配：

- 当前参数：`size`
- 配套参数：
  - `transform_model_param`
  - `transform_width_param`
  - `transform_height_param`
  - `transform_media_param`
  - `transform_sequential_param`

示例：

```json
"name": "size",
"transform": "custom_size",
"transform_model_param": "model",
"transform_width_param": "custom_width",
"transform_height_param": "custom_height",
"transform_media_param": "images",
"transform_sequential_param": "enable_sequential"
```

### 8.2 `bbox_list`

- 用途：把字符串形式的 JSON 解析成数组，并按输入图片数量做校验
- 常见搭配：

```json
"transform": "bbox_list",
"transform_media_param": "images"
```

### 8.3 `color_palette`

- 用途：解析颜色列表 JSON，并在某些模式下做限制
- 常见搭配：

```json
"transform": "color_palette",
"transform_sequential_param": "enable_sequential"
```

### 8.4 `json`

- 用途：把字符串 JSON 直接解析成对象

## 9. transform 辅助字段

这些字段只在对应 transform 下有意义。

### `transform_model_param`

- 给 `custom_size` 用
- 指定“从哪个参数读取 model”

### `transform_width_param`

- 给 `custom_size` 用
- 指定“从哪个参数读取宽度”

### `transform_height_param`

- 给 `custom_size` 用
- 指定“从哪个参数读取高度”

### `transform_media_param`

- 给 `custom_size` / `bbox_list` 用
- 指定“关联哪个媒体参数”

### `transform_sequential_param`

- 给 `custom_size` / `color_palette` 用
- 指定“关联哪个布尔参数”

## 10. 当前 payload builder 的行为规则

下面是当前代码中的实际规则总结。

### 10.1 `model` 字段如何决定

优先级从高到低：

1. `request_model_from`
2. `request_model`
3. `model_key`

### 10.2 普通参数如何写入 payload

普通参数处理顺序：

1. 先读取 `kwargs[name]`
2. 如果配置了 `transform`，先执行 transform
3. 再用 `send_if` / `only_if_*` / `skip_values` 判断是否发送
4. 最终写入 `payload[api_field]`

### 10.3 媒体参数如何写入 payload

媒体参数处理顺序：

1. 收集单个或多个输入值
2. 如果 `inputcount_param` 存在，按其值限制读取数量
3. 如果 `flatten_batches=true`，展开图片 batch
4. 上传媒体，得到 URL
5. 根据配置写入 payload：
   - `media_item_type` 存在：聚合成对象数组
   - `multiple_inputs` / `multiple` / `force_list`：写成 URL 数组
   - 否则：写成单个 URL

### 10.4 `internal=true` 的参数

- 会出现在节点输入层
- 不会直接进入 payload
- 但仍然可以被其他规则引用

## 11. 推荐写法模式

### 11.1 最简单节点

只写基础字段：

```json
{
  "internal_name": "BizyTRD_SimpleTextToImage",
  "class_name": "BizyTRDSimpleTextToImage",
  "display_name": "BizyTRD Simple Text To Image",
  "category": "BizyTRD/Test",
  "model_key": "simple-text-to-image",
  "output_type": "image",
  "params": [
    {
      "name": "prompt",
      "api_field": "prompt",
      "type": "STRING",
      "required": true,
      "multiline": true
    }
  ]
}
```

### 11.2 多图输入节点

```json
{
  "name": "images",
  "api_field": "imageUrls",
  "type": "IMAGE",
  "multiple_inputs": true,
  "max_inputs": 4,
  "extra_input_pattern": "image_{index}"
}
```

### 11.3 带 inputcount 的多图输入

```json
{
  "name": "images",
  "api_field": "imageUrls",
  "type": "IMAGE",
  "multiple_inputs": true,
  "max_inputs": 9,
  "inputcount_param": "inputcount",
  "extra_input_pattern": "image_{index}"
},
{
  "name": "inputcount",
  "type": "INT",
  "internal": true,
  "default": 1
}
```

### 11.4 同字段媒体对象数组

```json
{
  "name": "video",
  "api_field": "media",
  "type": "VIDEO",
  "media_item_type": "video"
},
{
  "name": "ref_image_1",
  "api_field": "media",
  "type": "IMAGE",
  "media_item_type": "reference_image"
}
```

### 11.5 不传默认值

```json
{
  "name": "ratio",
  "api_field": "ratio",
  "type": "LIST",
  "default": "default",
  "send_if": "not_default"
}
```

### 11.6 隐藏控制参数

```json
{
  "name": "custom_width",
  "type": "INT",
  "internal": true
}
```

## 12. 当前不建议做的事

### 不要再引入大段模型专属 DSL

当前设计方向就是避免重新回到：

- `context`
- `validators`
- `payload` mini-language

如果一个新需求可以通过扩展现有通用字段解决，优先扩展通用字段。

### 不要把 UI 含义和 payload 含义混在一起

例如：

- `required` 是节点输入层面的概念
- `send_if` 是 payload 层面的概念

两者不是同一回事。

### 不要滥用 `internal`

`internal=true` 的参数虽然不直接发给后端，但仍然会出现在节点输入里。

如果一个字段既不需要显示给用户，也不需要参与通用 builder 逻辑，就不应该放进 registry。

## 13. 新增节点时的推荐流程

1. 先写最小模型定义：
   - `internal_name`
   - `class_name`
   - `display_name`
   - `category`
   - `model_key`
   - `output_type`
   - `params`
2. 先假设所有参数都按 `name -> api_field` 直接映射
3. 如果有多媒体输入，再补：
   - `multiple_inputs`
   - `max_inputs`
   - `extra_input_pattern`
   - `inputcount_param`
4. 如果有条件发送，再补：
   - `send_if`
   - `only_if_*`
   - `skip_values`
5. 如果 `model` 来源特殊，再补：
   - `request_model`
   - `request_model_from`
6. 如果普通映射仍然不够，再考虑扩展通用 builder，而不是先写模型专属逻辑

## 14. 当前实现的已知边界

下面这些点要明确：

- 当前 `required` 不会自动转化成 payload 层校验
- `require_any_of` 是模型级“至少一个非空”校验，不是完整规则引擎
- `transform` 当前只支持少量内建类型
- 参数之间的复杂交叉校验还没有做成通用 schema
- `node_factory` 只负责生成输入口，不负责前端动态隐藏/显示逻辑

所以 registry 已经足够覆盖当前仓库里的节点，但它还不是一个无限通用的规则系统。

## 15. 一句话总结

`models_registry.json` 的推荐使用方式是：

- 用它定义节点和参数
- 用少量参数级元数据表达通用 payload 规则
- 避免回到“每个模型一份复杂专属逻辑”的写法
