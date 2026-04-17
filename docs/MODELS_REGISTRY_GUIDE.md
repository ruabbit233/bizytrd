# Models Registry Guide

这份文档描述当前仓库里 [`models_registry.json`](/Users/huhuhu/Desktop/refactor/bizytrd/models_registry.json) 的实际 schema。

核心原则只有三条：

1. `category` 只用于 ComfyUI 菜单展示
2. endpoint 由 `model_name` 和 `endpoint_category` 组装
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
- `defaultValue`
- `description`
- `multiline`
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
  "multipleInputs": true,
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
- `multipleInputs = true`
- `name` 是 `image` / `images` / `video` / `videos` / `audio` / `audios`

系统会自动补：

- `image_inputcount`
- `video_inputcount`
- `audio_inputcount`

并且最大数量直接取媒体参数上的 `maxInputNum`。

### 兼容字段

- `inputcountParam`
  - 仍兼容，但新节点不建议再写
- `max_inputs`
  - 仍兼容，优先改成 `maxInputNum`

## 5. payload 构建相关字段

- `internal`
  - 输入存在，但不直接发给后端
- `flattenBatches`
  - 图片 batch 展平
- `forceList`
  - 即使单输入也强制发数组
- `mediaItemType`
  - 聚合同一 `fieldKey` 下的媒体对象数组
- `sendIf`
- `skipValues`
- `onlyIfTrueParam`
- `onlyIfFalseParam`
- `onlyIfMediaAbsent`
- `onlyIfMediaPresent`

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

不再通过 registry 传 `hook*Param` 这类辅助字段。provider-specific hook 直接按当前节点约定读取固定参数名。

例如：

```json
{
  "name": "size",
  "fieldKey": "size",
  "type": "LIST",
  "valueHook": "wan.custom_size"
}
```

## 7. 推荐模式

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
  "multipleInputs": true,
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

### 同字段媒体对象数组

```json
{
  "name": "video",
  "fieldKey": "media",
  "type": "VIDEO",
  "mediaItemType": "video"
},
{
  "name": "ref_image_1",
  "fieldKey": "media",
  "type": "IMAGE",
  "mediaItemType": "reference_image"
}
```

## 8. 不建议再做的事

- 不要再在 registry 里写 `transform`
- 不要再手写默认的 `image_inputcount` / `video_inputcount` / `audio_inputcount`
- 不要把 UI 展示字段和 endpoint 路由字段混在一起
- 不要为单个模型新增专属 adapter，优先扩展统一 builder 或有限 hook
