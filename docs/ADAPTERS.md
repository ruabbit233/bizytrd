# Payload Builder

当前版本不再鼓励“每个模型写一个 adapter 函数”。

目标是尽量接近 `ComfyUI_RH_OpenAPI` 的思路：

- 节点生成逻辑通用化
- payload 构建逻辑通用化
- registry 只补少量必要元数据

## 1. 基本原则

大多数节点应该只写：

- 节点基础信息
- `params`

只有在默认一一映射不够时，才给参数补充少量元数据，而不是再写一段完整 adapter。

## 2. 当前通用 payload builder 支持什么

[`core/adapters.py`](/Users/huhuhu/Desktop/refactor/bizytrd/core/adapters.py) 现在是一个统一 builder，支持下面这些通用能力：

- 普通参数直接按 `api_field` 写入 payload
- 媒体参数自动上传
- `multiple_inputs + max_inputs + extra_input_pattern`
- `inputcount_param`
- 图片批量输入展开 `flatten_batches`
- 多媒体直接聚合成 URL 数组
- 多个媒体参数按 `media_item_type` 聚合成对象数组
- 简单发送条件：
  - `send_if: non_empty`
  - `send_if: true`
  - `send_if: gte_zero`
  - `send_if: nonzero`
  - `send_if: not_default`
- 简单条件依赖：
  - `only_if_true_param`
  - `only_if_false_param`
  - `only_if_media_absent`
  - `only_if_media_present`
- 少量通用 transform：
  - `custom_size`
  - `bbox_list`
  - `color_palette`
  - `json`

## 3. registry 新增的元数据

### 模型级

- `request_model`
  - 固定覆盖 payload 里的 `model`
- `request_model_from`
  - 从某个输入参数取 payload 里的 `model`
- `require_any_of`
  - 至少要求这些输入中的一个非空
- `require_any_message`
  - 自定义错误提示

### 参数级

- `internal`
  - 节点输入存在，但不直接发给后端
- `inputcount_param`
  - 多输入媒体读取多少个端口
- `flatten_batches`
  - 图片输入按 batch 展开
- `media_item_type`
  - 把媒体拼成对象数组项
- `upload_file_name_prefix`
- `upload_total_pixels`
- `upload_max_size`
- `upload_format`
- `upload_duration_range`
- `send_if`
- `only_if_true_param`
- `only_if_false_param`
- `only_if_media_absent`
- `only_if_media_present`
- `transform`

## 4. 为什么这样比命名 adapter 更合适

因为它把“复杂节点的差异”压回到了通用规则里。

新增一个节点时，优先顺序应该是：

1. 先只写 `params`
2. 如果不够，再补参数元数据
3. 只有通用 builder 真的表达不了时，才考虑新增代码

这比“每来一个复杂模型就新增一个 Python adapter 函数”更符合长期目标。

## 5. 当前三个复杂模型是怎么落到通用规则里的

### Wan 2.7 Image

主要依赖：

- `request_model_from`
- `require_any_of`
- `inputcount_param`
- `flatten_batches`
- `transform: custom_size`
- `transform: bbox_list`
- `transform: color_palette`
- `send_if`

### Wan 2.7 Video Edit

主要依赖：

- 多个媒体参数共享 `api_field = media`
- 每个媒体参数声明自己的 `media_item_type`

这样 builder 会自动拼出：

```json
[
  {"type": "video", "url": "..."},
  {"type": "first_frame", "url": "..."},
  {"type": "reference_image", "url": "..."}
]
```

### Seedance 2.0 Multimodal

主要依赖：

- `request_model`
- `require_any_of`
- 三组媒体参数各自声明 `inputcount_param`
- 自动聚合成 `imageUrls` / `videoUrls` / `audioUrls`

## 6. 新增节点的建议

如果一个新节点满足 RH 风格的通用结构：

- 普通字段直接传
- 媒体字段上传后传 URL
- 多输入媒体传数组
- 同字段多媒体传对象数组

那就不需要新 adapter。

只有真出现新的“全新类别能力”时，才扩展 builder 本身，而不是先写一个新的模型专属函数。
