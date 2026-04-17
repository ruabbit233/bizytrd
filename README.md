# bizytrd

`bizytrd` 是一个面向 BizyAir 第三方模型接入的新项目，用于为 ComfyUI 提供统一、清晰、可扩展的节点层。

它的目标被有意收敛为一件事：

- 为 BizyAir 第三方模型提供一套干净的、由 registry 驱动的 OpenAPI 风格节点层
- 对接 BizyAir 自有后端接口，例如 `silicon-cloud-x`
- 替代当前 `bizyengine/bizyair_extras/third_party_api` 下不断扩张的手写节点实现

这个仓库目前是第一版设计与脚手架落地，不是最终生产可用形态。

## 开发环境

当前项目默认使用 `conda` 的 `comfyenv` 环境进行开发和测试。

推荐命令：

```bash
conda run -n comfyenv python -m pytest -v
```

如果需要进入交互式环境，也统一使用：

```bash
conda activate comfyenv
```

## 为什么要做这个项目

当前 BizyAir 的第三方节点虽然能用，但整体结构不利于继续扩展：

- 节点定义分散在很多 Python 文件中
- 输入 schema 和 payload 映射大多是按类手写
- 前端节点定义和后端 registry 容易逐渐漂移
- 每增加一个新的 provider，通常都要手动改动多层代码

`bizytrd` 借鉴了 `ComfyUI_RH_OpenAPI` 比较清晰的高层思路：

- 以模型 registry 作为节点定义的主要来源
- 对通用场景使用动态节点生成
- 对复杂模型使用少量参数级元数据，而不是为每个节点单独写 payload 逻辑
- 明确划分 ComfyUI 插件、BizyAir API 网关、provider 代理逻辑之间的边界

## 当前已包含的内容

当前脚手架已经包含：

- 一套推荐的项目结构
- 第一版架构设计文档
- 从现有 `third_party_api` 迁移过来的迁移计划
- 一个初始版本的 `models_registry.json`
- 一个最小可用的 ComfyUI 节点工厂入口
- 一套可工作的 BizyAir 媒体上传客户端
- 基于通用 payload builder 的 `wan2.7-videoedit` 和 `wan2.7-image` 支持
- 以 Python 包方式导出，便于 `BizyAirAir` 像使用 `bizyengine` 一样引入 `bizytrd`
- 一个用于把前端资源同步到 `BizyAirAir/js` 的 web 资源同步工具

## 打包与接入模式

`bizytrd` 现在的定位是一个只供 `BizyAirAir` 引入的可复用 Python 包。

它不再作为独立的 ComfyUI custom node 入口直接加载。

这个包当前导出的复用入口包括：

- `get_node_mappings()`
- `get_web_directory()`
- `sync_web_assets(target_dir)`

节点密钥不再逐节点配置。`bizytrd` 只通过环境变量和 `api_key.ini` 约定读取共享的 BizyAirAir 风格配置，推荐优先使用 `BIZYAIR_API_KEY`。它在运行时不会 import `bizyengine`。

推荐的生产接入方式是：

1. 将 `bizytrd` 发布为 Python 包
2. 让 `BizyAirAir` 依赖 `bizytrd`
3. 在 `BizyAirAir/__init__.py` 中导入 `bizytrd` 的节点，并把 `bizytrd` 的前端 JS 同步到 `BizyAirAir/js`

这样可以保证 `BizyAirAir` 仍然是唯一的业务入口，同时第三方节点层又可以独立演进。

## Registry 元数据说明

`models_registry.json` 不支持 JSON 注释，因此参数说明应该写成每个 `param` 上的结构化元数据，而不是写成注释。

推荐字段如下：

- `description`：参数说明。当前项目只保留这一种说明字段
- `multiple_inputs`：把一个媒体参数展开成 `images + image_2..image_N` 这种额外输入口
- `inputcount_param`：当媒体参数支持动态多输入时，读取哪个 `INT` 参数来控制实际使用的输入数量

当前约定是：

- 如果媒体参数配置了 `inputcount_param`，则最大输入数量由对应 `inputcount` 参数的 `max` 决定，不再单独写 `max_inputs`
- 多输入命名规则固定为：
  - 参数名是复数时，附加输入口使用去掉尾部 `s` 后的形式，例如 `images -> image_2`
  - 否则使用 `<name>_2`、`<name>_3`
- 媒体上传文件命名、大小限制等策略由代码内统一处理，不再放在 registry 中配置

在实际使用中，建议每个 `param` 至少带一个说明字段，这样 registry 本身可读性更强，生成出来的节点也能保持自解释。

如果某些模型需要兼容老 BizyAir 风格的 `inputcount` 行为，可以把 `inputcount` 作为普通 `INT` 参数保留在 registry 中，再让通用 payload builder 通过参数元数据去读取它。这样既能保持节点定义的声明式风格，也能支持多图聚合这类能力。

## 推荐的后端边界

`bizytrd` 应该调用 BizyAir 自有 API，而不是直接对接各个 provider 的 API。

推荐链路如下：

1. ComfyUI 节点采集输入
2. 本地媒体通过 BizyAir 自有上传接口归一化上传
3. 节点向 `silicon-cloud-x` 提交任务
4. `silicon-cloud-x` 通过自己的 registry 解析模型
5. `bizyair-trd-proxy` 负责处理 provider 侧的细节
6. ComfyUI 轮询 BizyAir 自有任务结果，并把输出转换回 Comfy 原生类型

## 建议目录结构

```text
bizytrd/
├── __init__.py
├── pyproject.toml
├── requirements.txt
├── models_registry.json
├── core/
│   ├── __init__.py
│   ├── base.py
│   ├── config.py
│   ├── upload.py
│   └── result.py
├── nodes/
│   ├── __init__.py
│   └── node_factory.py
└── docs/
    ├── ARCHITECTURE.md
    └── MIGRATION_PLAN.md
```

## 重要设计决策

长期来看，真正的单一事实来源不应该只存在于 Python 代码里。

更理想的目标是：

- 定义一份共享的 BizyAir TRD manifest
- 后端 registry 从这份 manifest 生成或加载
- 前端节点 registry 也从同一份 manifest 生成

这样可以保持下面两层长期一致：

- `ComfyUI/custom_nodes/bizytrd`
- `silicon-cloud-x/service/registry.go`

## 下一步建设建议

1. 继续把新的上传客户端复用到更多图像和视频节点中，不要只停留在 `wan2.7-videoedit`
2. 为仍然依赖预上传 URL 的节点补齐音频上传支持
3. 继续扩展 `models_registry.json`，从当前种子集合逐步变成完整目录
4. 优先迁移 Wan、Vidu、GPT Image，再继续推进 Kling、Sora、Veo、Hailuo、Doubao
5. 只有在 BizyAir 后端确实需要时，再补充资产类 helper 节点
