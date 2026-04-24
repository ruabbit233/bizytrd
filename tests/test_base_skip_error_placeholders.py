import importlib
import io
import sys
import types


class _FakeTensor:
    def __init__(self, array):
        self.array = array

    def unsqueeze(self, dim):
        return self

    def repeat(self, *sizes):
        return _FakeRepeatedTensor(self, sizes)


class _FakeRepeatedTensor:
    def __init__(self, source, sizes):
        self.source = source
        self.sizes = sizes


def _import_base_with_stubs(monkeypatch):
    fake_torch = types.SimpleNamespace(
        Tensor=_FakeTensor,
        from_numpy=lambda array: _FakeTensor(array),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    comfy_api_latest_module = types.ModuleType("comfy_api.latest")

    class FakeVideoComponents:
        def __init__(self, images, frame_rate, audio=None, metadata=None):
            self.images = images
            self.frame_rate = frame_rate
            self.audio = audio
            self.metadata = metadata

    class FakeVideoFromComponents:
        def __init__(self, components):
            self.components = components

    comfy_api_latest_module.InputImpl = types.SimpleNamespace(
        VideoFromComponents=FakeVideoFromComponents
    )
    comfy_api_latest_module.Types = types.SimpleNamespace(
        VideoComponents=FakeVideoComponents
    )
    monkeypatch.setitem(sys.modules, "comfy_api.latest", comfy_api_latest_module)

    comfy_api_module = types.ModuleType("comfy_api")
    comfy_api_input_impl_module = types.ModuleType("comfy_api.latest._input_impl")

    class FakeVideoFromFile:
        def __init__(self, file_obj):
            self.payload = file_obj.read()

    comfy_api_input_impl_module.VideoFromFile = FakeVideoFromFile
    monkeypatch.setitem(sys.modules, "comfy_api", comfy_api_module)
    monkeypatch.setitem(
        sys.modules,
        "comfy_api.latest._input_impl",
        comfy_api_input_impl_module,
    )

    sys.modules.pop("bizytrd.core.base", None)
    base = importlib.import_module("bizytrd.core.base")
    return importlib.reload(base), FakeVideoFromFile, FakeVideoFromComponents


def test_make_placeholder_video_prefers_comfy_video_components(monkeypatch):
    base, _, fake_video_type = _import_base_with_stubs(monkeypatch)

    placeholder = base._make_placeholder_video("boom placeholder")

    assert isinstance(placeholder, fake_video_type)
    assert placeholder.components.images.sizes == (24, 1, 1, 1)


def test_execute_skip_error_returns_dynamic_image_placeholder(monkeypatch):
    base, _, _ = _import_base_with_stubs(monkeypatch)

    class ImageNode(base.BizyTRDBaseNode):
        OUTPUT_TYPE = "image"

        async def _create_task_and_wait(self, *args, **kwargs):
            raise RuntimeError("image generation failed")

    node = ImageNode()
    node.build_payload = lambda config, **kwargs: {}
    node.resolve_endpoint = lambda **kwargs: "test/image"

    result = base.asyncio.run(node.execute(skip_error=True))

    image_output, urls_str = result["result"]
    assert isinstance(image_output, _FakeTensor)
    assert urls_str == ""
    assert result["ui"]["text"] == [""]


def test_execute_skip_error_returns_dynamic_video_placeholder(monkeypatch):
    base, _, fake_video_type = _import_base_with_stubs(monkeypatch)

    class VideoNode(base.BizyTRDBaseNode):
        OUTPUT_TYPE = "video"

        async def _create_task_and_wait(self, *args, **kwargs):
            self.original_urls.add("https://example.com/original.mp4")
            raise RuntimeError("video generation failed")

    node = VideoNode()
    node.build_payload = lambda config, **kwargs: {}
    node.resolve_endpoint = lambda **kwargs: "test/video"
    result = base.asyncio.run(node.execute(skip_error=True))

    video_output, urls_str = result["result"]
    assert isinstance(video_output, fake_video_type)
    assert urls_str == '["https://example.com/original.mp4"]'
    assert result["ui"]["text"] == ['["https://example.com/original.mp4"]']


def test_execute_skip_error_for_text_output_surfaces_error_message(monkeypatch):
    base, _, _ = _import_base_with_stubs(monkeypatch)

    class TextNode(base.BizyTRDBaseNode):
        OUTPUT_TYPE = "string"

        async def _create_task_and_wait(self, *args, **kwargs):
            raise RuntimeError("text generation failed")

    node = TextNode()
    node.build_payload = lambda config, **kwargs: {}
    node.resolve_endpoint = lambda **kwargs: "test/text"

    result = base.asyncio.run(node.execute(skip_error=True))

    primary, urls_str = result["result"]
    assert primary == "text generation failed"
    assert urls_str == ""
    assert result["ui"]["text"] == ["text generation failed", ""]
