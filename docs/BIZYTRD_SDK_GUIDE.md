# BizyTRD SDK 使用指南

`bizytrd` 当前仓库内包含一个可复用的 SDK，当前包路径为 `bizytrd.bizytrd_sdk`。

如果后续把 SDK 拆成与 `bizytrd` 平行的独立包，推荐对外导入形式是：

```python
from bizytrd_sdk import AsyncBizyTRD, BizyTRD
```

当前仓库内的实际导入路径仍然是：

```python
from bizytrd.bizytrd_sdk import AsyncBizyTRD, BizyTRD
```

这个 SDK 的目标是把 BizyAir 第三方节点中的网络请求、任务轮询、上传逻辑抽离出来，供：

- `bizytrd` 主项目内部复用
- `BizyAir` 这类上层插件调用
- 后续独立测试或迁移时复用

## 设计边界

SDK 的同步/异步边界与 `bizyengine/bizyair_extras/third_party_api` 保持一致：

- 任务创建、状态轮询、结果下载：异步
- 上传 token 获取、OSS 文件上传：同步

对应类型：

- `AsyncBizyTRD`：负责异步任务链路
- `BizyTRD`：负责同步上传链路

## 导入方式

```python
from bizytrd.bizytrd_sdk import AsyncBizyTRD, BizyTRD, SDKConfig, get_config
```

如果你在 `bizytrd` 包内部调用，优先使用相对导入：

```python
from ..bizytrd_sdk import AsyncBizyTRD, BizyTRD
```

## 配置方式

推荐方式是显式构造配置，并在创建 client 时传入：

```python
from bizytrd.bizytrd_sdk import AsyncBizyTRD, SDKConfig

config = SDKConfig(
    api_key="your-api-key",
    base_url="https://uat-api.bizyair.cn/x/v1",
    upload_base_url="https://uat-api.bizyair.cn/x/v1",
    timeout=60,
    polling_interval=10,
    max_polling_time=3600,
)

client = AsyncBizyTRD(
    api_key=config.api_key,
    base_url=config.base_url,
    upload_base_url=config.upload_base_url,
    timeout=config.timeout,
    polling_interval=config.polling_interval,
    max_polling_time=config.max_polling_time,
)
```

同步上传客户端同理：

```python
from bizytrd.bizytrd_sdk import BizyTRD, SDKConfig

config = SDKConfig(
    api_key="your-api-key",
    base_url="https://uat-api.bizyair.cn/x/v1",
    upload_base_url="https://uat-api.bizyair.cn/x/v1",
)

client = BizyTRD(
    api_key=config.api_key,
    base_url=config.base_url,
    upload_base_url=config.upload_base_url,
)
```

只有在你不显式传参时，SDK 才会回退到环境变量和本地 `api_key.ini`。

## 环境变量兜底

如果你不想在代码里硬编码，可以使用这些环境变量：

- `BIZYTRD_API_KEY`
- `BIZYTRD_BASE_URL`
- `BIZYAIR_API_KEY`
- `BIZYAIR_TEST_TRD_BASE_URL`
- `BIZYTRD_API_BASE_URL`
- `BIZYTRD_SERVER_URL`
- `BIZYTRD_UPLOAD_BASE_URL`
- `BIZYTRD_UPLOAD_URL`
- `BIZYTRD_API_KEY_PATH`
- `BIZYTRD_TIMEOUT`
- `BIZYTRD_POLLING_INTERVAL`
- `BIZYTRD_MAX_POLLING_TIME`

本地文件兜底只保留：

- 当前工作目录下的 `api_key.ini`
- `~/.config/bizytrd/api_key.ini`
- `~/.bizytrd/api_key.ini`

快速查看当前解析结果：

```python
from bizytrd.bizytrd_sdk import get_config

config = get_config()
print(config)
```

## 1. 异步任务调用

最常见的调用流程是：

1. 创建任务
2. 轮询直到完成
3. 下载输出内容

示例：

```python
import asyncio

from bizytrd.bizytrd_sdk import AsyncBizyTRD, SDKConfig


async def main():
    config = SDKConfig(
        api_key="your-api-key",
        base_url="https://uat-api.bizyair.cn/x/v1",
        upload_base_url="https://uat-api.bizyair.cn/x/v1",
        timeout=60,
        polling_interval=10,
        max_polling_time=3600,
    )

    payload = {
        "model": "wan2.7-image-pro",
        "prompt": "a cinematic mountain lake at sunrise",
    }

    async with AsyncBizyTRD(
        api_key=config.api_key,
        base_url=config.base_url,
        upload_base_url=config.upload_base_url,
        timeout=config.timeout,
        polling_interval=config.polling_interval,
        max_polling_time=config.max_polling_time,
    ) as client:
        task = await client.create_task("wan2.7-image", payload)
        result = await client.wait_for_task(task.request_id)
        downloaded = await client.download_outputs(result.outputs)

        print("request_id:", result.request_id)
        print("status:", result.status)
        print("urls:", downloaded.urls)
        print("image count:", len(downloaded.images))
        print("text outputs:", downloaded.texts)


asyncio.run(main())
```

## 2. 使用 `responses` 风格接口

SDK 也提供了一个更贴近通用 client 风格的入口：

```python
import asyncio

from bizytrd.bizytrd_sdk import AsyncBizyTRD, SDKConfig


async def main():
    config = SDKConfig(
        api_key="your-api-key",
        base_url="https://uat-api.bizyair.cn/x/v1",
        upload_base_url="https://uat-api.bizyair.cn/x/v1",
        timeout=60,
        polling_interval=10,
        max_polling_time=3600,
    )

    async with AsyncBizyTRD(
        api_key=config.api_key,
        base_url=config.base_url,
        upload_base_url=config.upload_base_url,
        timeout=config.timeout,
        polling_interval=config.polling_interval,
        max_polling_time=config.max_polling_time,
    ) as client:
        task = await client.responses.create(
            model="wan2.7-image",
            input={
                "model": "wan2.7-image-pro",
                "prompt": "a futuristic city street after rain",
            },
        )
        result = await task.wait()
        print(result.output_urls)


asyncio.run(main())
```

## 3. 查询已有任务

如果你已经拿到了 `request_id`，可以单独查询：

```python
import asyncio

from bizytrd.bizytrd_sdk import AsyncBizyTRD, SDKConfig


async def main():
    config = SDKConfig(
        api_key="your-api-key",
        base_url="https://uat-api.bizyair.cn/x/v1",
        upload_base_url="https://uat-api.bizyair.cn/x/v1",
        timeout=60,
        polling_interval=10,
        max_polling_time=3600,
    )

    async with AsyncBizyTRD(
        api_key=config.api_key,
        base_url=config.base_url,
        upload_base_url=config.upload_base_url,
        timeout=config.timeout,
        polling_interval=config.polling_interval,
        max_polling_time=config.max_polling_time,
    ) as client:
        payload = await client.retrieve_task("your-request-id")
        print(payload)


asyncio.run(main())
```

## 4. 同步上传文件

上传链路使用同步客户端 `BizyTRD`：

```python
from bizytrd.bizytrd_sdk import BizyTRD, SDKConfig

config = SDKConfig(
    api_key="your-api-key",
    base_url="https://uat-api.bizyair.cn/x/v1",
    upload_base_url="https://uat-api.bizyair.cn/x/v1",
)

client = BizyTRD(
    api_key=config.api_key,
    base_url=config.base_url,
    upload_base_url=config.upload_base_url,
)
url = client.upload_file("/path/to/example.webp")
print(url)
```

上传二进制内容：

```python
import io

from bizytrd.bizytrd_sdk import BizyTRD, SDKConfig

config = SDKConfig(
    api_key="your-api-key",
    base_url="https://uat-api.bizyair.cn/x/v1",
    upload_base_url="https://uat-api.bizyair.cn/x/v1",
)

client = BizyTRD(
    api_key=config.api_key,
    base_url=config.base_url,
    upload_base_url=config.upload_base_url,
)

bio = io.BytesIO(b"example-bytes")
url = client.upload_bytes(bio, "example.bin")
print(url)
```

只获取上传凭证：

```python
from bizytrd.bizytrd_sdk import BizyTRD, SDKConfig

config = SDKConfig(
    api_key="your-api-key",
    base_url="https://uat-api.bizyair.cn/x/v1",
    upload_base_url="https://uat-api.bizyair.cn/x/v1",
)

client = BizyTRD(
    api_key=config.api_key,
    base_url=config.base_url,
    upload_base_url=config.upload_base_url,
)
token = client.request_upload_token("example.webp")
print(token)
```

## 5. Prompt ID 透传

如果你在 ComfyUI 或 BizyAir 上层已经持有 `prompt_id`，可以透传到请求头：

```python
task = await client.create_task(
    "wan2.7-image",
    payload,
    prompt_id="your-prompt-id",
)
```

轮询时同样支持：

```python
result = await client.wait_for_task(
    task.request_id,
    prompt_id="your-prompt-id",
)
```

## 6. 返回类型说明

### `TaskHandle`

- `request_id`
- `model`
- `raw_payload`
- `retrieve()`
- `wait()`
- `download_outputs()`

### `TaskResult`

- `request_id`
- `status`
- `outputs`
- `raw_payload`
- `original_urls`
- `output_urls`
- `output_texts`

### `DownloadedOutputs`

- `videos`：`list[bytes]`
- `images`：`list[bytes]`
- `texts`：`list[str]`
- `urls`：`list[str]`

注意：SDK 下载后的媒体内容是原始 `bytes`。如果你在 ComfyUI 节点中使用，还需要在上层自行转成：

- `VideoFromFile`
- 图片 tensor
- 其他业务需要的对象

## 7. 在 bizytrd 项目中的推荐用法

当前项目里的推荐分工是：

- `core/base.py`：调用 `AsyncBizyTRD` 提交任务、轮询结果、下载输出
- `core/upload.py`：调用 `BizyTRD` 做同步上传
- `core/result.py`：把 SDK 下载得到的 bytes 转成 ComfyUI 侧对象

也就是说：

- SDK 负责网络传输和结果原始下载
- `bizytrd` 主项目负责 payload 组装和 ComfyUI 类型适配

## 8. 异常类型

SDK 暴露的主要异常：

- `BizyTRDError`
- `BizyTRDConnectionError`
- `BizyTRDPermissionError`
- `BizyTRDResponseError`
- `BizyTRDTimeoutError`

示例：

```python
import asyncio

from bizytrd.bizytrd_sdk import AsyncBizyTRD, BizyTRDTimeoutError, SDKConfig


async def main():
    try:
        config = SDKConfig(
            api_key="your-api-key",
            base_url="https://uat-api.bizyair.cn/x/v1",
            upload_base_url="https://uat-api.bizyair.cn/x/v1",
            timeout=60,
            polling_interval=10,
            max_polling_time=30,
        )
        async with AsyncBizyTRD(
            api_key=config.api_key,
            base_url=config.base_url,
            upload_base_url=config.upload_base_url,
            timeout=config.timeout,
            polling_interval=config.polling_interval,
            max_polling_time=config.max_polling_time,
        ) as client:
            task = await client.create_task("wan2.7-image", {"model": "wan2.7-image-pro", "prompt": "test"})
            await task.wait()
    except BizyTRDTimeoutError as exc:
        print("task timed out:", exc)


asyncio.run(main())
```

## 9. 注意事项

- `AsyncBizyTRD.download_outputs()` 返回的是原始字节，不是 ComfyUI 对象。
- 在当前 monorepo 内部引用 SDK，不要写顶层 `from bizytrd_sdk import ...`，应使用包内相对导入。
- `sync_web_assets()` 属于节点前端资源同步逻辑，不属于 SDK 范围。
- 上传接口默认 `file_type="inputs"`，当前与 BizyAir 第三方节点实现保持一致。

## 10. 适用场景

适合直接使用 SDK 的场景：

- 需要独立测试某个第三方模型接口
- 需要把 BizyAir 第三方节点网络层拆分出去复用
- 需要在不依赖 ComfyUI 节点对象的情况下完成提交、轮询、下载

不适合只靠 SDK 解决的场景：

- 直接生成 ComfyUI 原生图片/视频对象
- 节点输入 schema 定义
- payload 参数映射和多媒体输入展开

这些仍然应由 `bizytrd` 主项目负责。
