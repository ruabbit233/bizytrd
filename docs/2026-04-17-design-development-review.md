# 2026-04-17 Design And Development Review

## 背景

本次审查的目标是评估当前 `bizytrd` 项目的设计与实现，重点围绕以下目标是否真正落地：

- 参考上层 [`ComfyUI_RH_OpenAPI`](/Users/huhuhu/Desktop/refactor/ComfyUI_RH_OpenAPI)
- 将上层 [`bizyengine/bizyair_extras/third_party_api`](/Users/huhuhu/Desktop/refactor/bizyengine/bizyengine/bizyair_extras/third_party_api) 中的第三方节点能力独立出来
- 以配置文件驱动 class 自动生成
- 将网络能力收敛为单独 SDK

当前结论是：方向正确，但还处在“架构验证和第一批种子节点落地”阶段，距离“可稳定替代旧实现、并作为上层可复用包长期演进”还有几处关键缺口。

## 总体判断

### 做对了的部分

- 已经形成了 `registry -> node_factory -> base node -> sdk` 的主链路，基础分层方向是对的
- 相比 `bizyengine` 的手写节点模式，当前实现明显降低了新增通用节点的代码成本
- `valueHook` 从 `adapters.py` 中拆出，避免 registry 回到任意逻辑执行的老路
- 已经有 `models_registry_migrated.json` 和迁移脚本，说明团队意识到了“先覆盖全量旧节点，再逐步清洗”的必要性

### 还没真正完成的部分

- “网络能力独立成 SDK” 只完成了一半，配置解析仍有双轨制
- “作为 Python 包供上层依赖” 的发布形态还不稳，源码可跑不代表安装产物可跑
- 当前主 `models_registry.json` 仍是小规模种子集合，距离替代 `third_party_api` 还有明显差距
- 音频能力的抽象已经暴露到节点层，但 SDK 和结果链路还没有完整闭环

## 主要问题

### 1. 高风险：发布产物与源码目录存在偏差，包安装后可能不完整

当前项目定位是一个供上层引入的可复用 Python 包，这一点在 [`README.md`](/Users/huhuhu/Desktop/refactor/bizytrd/README.md#L59) 中写得很清楚。

但当前打包配置存在明显风险：

- [`pyproject.toml`](/Users/huhuhu/Desktop/refactor/bizytrd/pyproject.toml#L13) 只显式声明了：
  - `bizytrd`
  - `bizytrd.core`
  - `bizytrd.nodes`
  - `bizytrd.bizytrd_sdk`
- 没有包含 `bizytrd.core.hooks`
- `package-data` 只包含 [`models_registry.json`](/Users/huhuhu/Desktop/refactor/bizytrd/models_registry.json) 和 `web/js/*.js`
- 没有包含运行时错误回退依赖的：
  - [`core/placeholder.png`](/Users/huhuhu/Desktop/refactor/bizytrd/core/placeholder.png)
  - [`core/placeholder.mp4`](/Users/huhuhu/Desktop/refactor/bizytrd/core/placeholder.mp4)

这和运行时代码是直接冲突的：

- [`core/adapters.py`](/Users/huhuhu/Desktop/refactor/bizytrd/core/adapters.py#L168) 会动态导入 `bizytrd.core.hooks.*`
- [`core/base.py`](/Users/huhuhu/Desktop/refactor/bizytrd/core/base.py#L42) 会读取占位资源

这意味着当前形态很容易出现下面的问题：

- 在源码目录中运行一切正常
- 打包发布后，某些 hook 无法导入
- 并发错误降级时，占位资源缺失
- 上层项目以依赖包方式引入时才暴露问题

这类问题会直接破坏当前项目最重要的交付目标，不应该后置。

### 2. 高风险：配置解析分散在节点层和 SDK，两套语义不一致

如果“网络能力要独立成 SDK”，那么配置解析原则上也应统一到 SDK。

但现在存在两套 `get_config()`：

- 节点侧 [`core/config.py`](/Users/huhuhu/Desktop/refactor/bizytrd/core/config.py#L115)
- SDK 侧 [`bizytrd_sdk/config.py`](/Users/huhuhu/Desktop/refactor/bizytrd/bizytrd_sdk/config.py#L92)

两套实现并不等价：

- [`core/config.py`](/Users/huhuhu/Desktop/refactor/bizytrd/core/config.py#L36) 会扫描 `BizyAir` 风格路径、`config/.env`、`BIZYAIR_COMFYUI_PATH`
- [`bizytrd_sdk/config.py`](/Users/huhuhu/Desktop/refactor/bizytrd/bizytrd_sdk/config.py#L34) 只扫描少量 SDK 自己的候选路径
- 两边环境变量优先级并不一致
- 两边兼容历史 BizyAir 配置的策略也不一致

结果是：

- 节点内部调用 SDK 时，实际使用的是节点侧配置解析结果
- 外部如果直接使用 SDK，拿到的可能是另一套配置结果

这和“SDK 是独立边界”的设计目标相冲突。长期看，这会导致：

- 同样的部署环境，在不同入口下行为不同
- 上层接入时更难排查配置问题
- 文档与真实运行语义逐渐分裂

### 3. 中风险：音频抽象已暴露，但 SDK 链路尚未闭环

当前节点工厂已经把 `AUDIO` 当作正式输入类型处理：

- [`nodes/node_factory.py`](/Users/huhuhu/Desktop/refactor/bizytrd/nodes/node_factory.py#L115)

当前 base node 也已经保留了 `audio` 输出分支：

- [`core/base.py`](/Users/huhuhu/Desktop/refactor/bizytrd/core/base.py#L247)

并且主 registry 中已经存在音频输入场景：

- `BizyTRD_Wan25ImageToVideo`
- `BizyTRD_Seedance20MultimodalVideo`

但 SDK 结果链路并没有完整支持音频：

- [`bizytrd_sdk/client.py`](/Users/huhuhu/Desktop/refactor/bizytrd/bizytrd_sdk/client.py#L366) 在 `saving` 状态只记录 `videos/images`
- [`bizytrd_sdk/client.py`](/Users/huhuhu/Desktop/refactor/bizytrd/bizytrd_sdk/client.py#L496) 下载输出时也只处理 `videos/images/texts`

这说明当前存在一个抽象提前暴露的问题：

- 节点层认为音频是正式媒体类型
- 上传层也支持音频输入
- 但下载与结果归一化链路并未形成完整对称

建议尽快明确其中一种路径：

- 要么正式补齐 SDK 的音频输出支持
- 要么在当前阶段明确限制为 image/video 主链路，不要过早暴露不完整抽象

### 4. 中风险：主 registry 的覆盖度不足以支撑“替代旧实现”

项目目标之一是替代旧的 `third_party_api` 手写节点体系，这在 [`README.md`](/Users/huhuhu/Desktop/refactor/bizytrd/README.md#L7) 中写得很明确。

但从当前实际覆盖度看：

- `third_party_api` 中继承 `BizyAirTrdApiBaseNode` 的类共有 67 个
- 当前主 [`models_registry.json`](/Users/huhuhu/Desktop/refactor/bizytrd/models_registry.json) 只有 12 个条目
- 当前主 registry 能直接映射到旧类的覆盖只有 9 个
- 全量覆盖只存在于迁移草稿 [`models_registry_migrated.json`](/Users/huhuhu/Desktop/refactor/bizytrd/models_registry_migrated.json)

这意味着当前仓库更准确的定位应该是：

- 一个新架构验证仓库
- 一个种子节点集合
- 一个全量迁移草稿生成器

而不是已经接近可替换旧系统的完整方案。

这不是坏事，但需要在项目认知上更诚实，否则很容易在后续迭代中误判成熟度。

## 架构评价

### 1. `registry -> class` 自动生成这条路是对的

当前最值得保留的，是节点工厂这条主链路：

- [`nodes/node_factory.py`](/Users/huhuhu/Desktop/refactor/bizytrd/nodes/node_factory.py)

它已经把以下问题处理成统一机制：

- 输入参数生成
- 多媒体输入展开
- `inputcount` 自动生成
- UI 输入顺序稳定化
- 返回类型映射

这部分比旧 `bizyengine` 的“每个类手写一份输入/上传/payload”要健康得多，应继续坚持。

### 2. `valueHook` 当前是合理折中，但要严格守边界

现在的 hook 机制已经明显比“在 registry 中写变换 DSL”更安全：

- hook 必须写成 `<module>.<function>`
- 只允许从 [`core/hooks`](/Users/huhuhu/Desktop/refactor/bizytrd/core/hooks) 中解析

这是正确方向。

但要注意一个边界问题：一旦 hook 逐渐变多，就很容易重新滑回“逻辑都塞进前端节点层”的老路。

建议对 hook 的职责做硬约束：

- 只允许值级别转换
- 不允许承担 provider 级任务编排
- 不允许承担网络调用
- 不允许承担复杂状态机

一旦某模型必须依赖复杂 hook 才能工作，就应优先判断：

- 是不是后端 template / registry 设计还不够成熟
- 是不是应该上收后端，而不是继续堆前端特判

### 3. 当前最缺的是“共享 manifest”，不是更多 Python 兼容逻辑

这一点 README 已经写到了，而且我认同这个方向：

- [`README.md`](/Users/huhuhu/Desktop/refactor/bizytrd/README.md#L138)

真正长期稳定的单一事实来源，不能只是一份前端专用 `models_registry.json`。

更理想的中期目标应当是：

- 定义 BizyAir TRD 共享 manifest
- 后端 registry 从 manifest 生成或加载
- 前端节点 registry 也从 manifest 生成

否则就算现在前端节点层做得更干净，未来仍然会和 `silicon-cloud-x` 的服务端 registry 漂移。

## 与参考项目的对照

### 相比 `ComfyUI_RH_OpenAPI`

当前 `bizytrd` 已经借鉴到了较好的部分：

- registry 驱动
- 工厂生成节点
- 尽量减少单节点 Python 手写逻辑

但还没完全借鉴到“发布完整性”和“工程闭环”这一层。

`ComfyUI_RH_OpenAPI` 更像一个已经面向实际节点发布和使用的工程；`bizytrd` 当前还偏“设计收敛中”。

### 相比 `bizyengine/bizyair_extras/third_party_api`

`bizytrd` 当前最大的价值，不是功能已经超过旧实现，而是开始把旧实现里高度重复的部分抽象出来：

- 上传逻辑
- payload 组装
- endpoint 组装
- 节点输入定义

这一点非常关键，也说明项目方向是值得继续投入的。

但旧系统里大量 provider-specific 行为还没有真正被“吸收进新边界”，只是先被迁移草稿记录下来了。

## 建议的下一步优先级

### 第一优先级：先修工程边界，而不是继续扩节点

建议先完成这三件事：

1. 修正打包配置
2. 补一个安装产物 smoke test
3. 统一配置解析入口

理由很简单：如果包发布形态和配置边界都没稳定，后面继续加 registry 条目，返工成本会更高。

### 第二优先级：把 SDK 真正做成单一网络边界

建议目标是：

- 节点层不再维护独立配置解析逻辑
- SDK 提供唯一 `Config` 解析与 client 初始化方式
- 节点层只补 ComfyUI 上下文，例如 `prompt_id`

这样才能真正做到：

- 网络能力独立
- 节点层只做 ComfyUI 适配
- 上层项目和节点内部使用同一套网络语义

### 第三优先级：以“迁移草稿清洗”为主，而不是直接手补主 registry

当前最合理的推进方式不是零散往主 registry 里加条目，而是：

1. 以 [`models_registry_migrated.json`](/Users/huhuhu/Desktop/refactor/bizytrd/models_registry_migrated.json) 为全量来源
2. 分 provider 清洗
3. 分批转正进入主 registry
4. 每转正一批，就补对应回归测试

这样能避免：

- 主 registry 与迁移草稿长期双轨分裂
- 团队只维护“少量手挑种子节点”，忽略整体替换目标

### 第四优先级：明确媒体能力矩阵

建议尽快在文档里明确：

- 当前正式支持哪些输入媒体类型
- 当前正式支持哪些输出媒体类型
- 哪些只是上传已支持、结果链路未闭环
- 哪些节点必须依赖后端 template 进行二次结构转换

不然现在代码读起来会给人一种“audio 已全面支持”的错觉，但实际上还没有。

## 验证说明

当前本地环境中没有可直接使用的 `pytest`：

- `pytest -q` 返回 `command not found`
- `python -m pytest -q` 返回 `No module named pytest`

仓库内文档 [`docs/2026-04-17-handoff.md`](/Users/huhuhu/Desktop/refactor/bizytrd/docs/2026-04-17-handoff.md#L177) 记录了在 `conda` 的 `comfyenv` 环境下于 2026-04-17 执行：

```bash
conda run -n comfyenv python -m pytest -v
```

文档声称结果为 17 个测试全部通过。

因此本次审查结论主要基于：

- 当前仓库源码结构
- 运行时关键路径
- 打包配置
- 上层参考项目对照
- 现有文档与测试覆盖范围

## 最终结论

`bizytrd` 当前最有价值的成果，不是“已经把旧系统替掉了”，而是已经找到了比旧系统更可持续的骨架。

这个骨架包括：

- registry 驱动的节点定义
- 有限 hook 的 payload builder
- 独立 SDK 的雏形
- 面向全量迁移的草稿 registry

但目前最需要警惕的是两件事：

- 不要把“种子架构已成立”误判成“工程已可发布替代”
- 不要在配置、hook、媒体能力这些边界还没收紧时继续快速扩张节点数

如果下一阶段先把“打包完整性、配置单一化、SDK 边界闭环”做扎实，这个项目是有机会真正替代旧 `third_party_api` 体系的。
