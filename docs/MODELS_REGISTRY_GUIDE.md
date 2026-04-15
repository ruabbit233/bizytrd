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

### 渠道相关字段

- `channelParam`
  - 可选，指定哪个参数控制渠道后缀，默认是 `channel`
- `channelSuffixMap`
  - 可选，渠道值到真正后缀的映射

如果 `channel` 为空，不修改 `model_name`。

例如：

```json
"model_name": "nano-banana-pro",
"channelSuffixMap": {
  "official": "official",
  "base": "base"
}
```

用户选择 `official` 时，endpoint 前半段会变成：

```text
nano-banana-pro-official
```

### payload model 相关字段

payload 中的 `model` 直接来自 `model_name`，再叠加可选的渠道后缀。

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

- `json_loads`
- `wan_custom_size`
- `wan_bbox_list`
- `wan_color_palette`

配套辅助字段统一使用 camelCase 的 `hook*` 命名，例如：

```json
{
  "name": "size",
  "fieldKey": "size",
  "type": "LIST",
  "valueHook": "wan_custom_size",
  "hookModelParam": "model",
  "hookWidthParam": "custom_width",
  "hookHeightParam": "custom_height",
  "hookMediaParam": "images",
  "hookSequentialParam": "enable_sequential"
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
  "valueHook": "json_loads"
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
