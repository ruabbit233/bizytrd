import json

from bizytrd.nodes.node_factory import create_all_nodes


def test_create_all_nodes_registers_manual_config_nodes():
    class_mappings, display_mappings = create_all_nodes()

    assert "BizyTRD_DoubaoToolConfig" in class_mappings
    assert display_mappings["BizyTRD_DoubaoToolConfig"] == "Doubao Tool Config"
    assert "BizyTRD_MultiPromptConfig" in class_mappings
    assert "BizyTRD_LLMToolConfig" in class_mappings


def test_manual_config_nodes_execute_locally():
    class_mappings, _ = create_all_nodes()

    doubao_node = class_mappings["BizyTRD_DoubaoToolConfig"]()
    assert doubao_node.execute(web_search=True) == (["web_search"],)
    assert doubao_node.execute(web_search=False) == ([],)

    multiprompt_node = class_mappings["BizyTRD_MultiPromptConfig"]()
    first_result = multiprompt_node.execute(prompt="first", duration=3)[0]
    assert json.loads(first_result) == [{"prompt": "first", "duration": 3}]

    second_result = multiprompt_node.execute(
        prompt="second",
        duration=5,
        prev_multi_prompt=first_result,
    )[0]
    assert json.loads(second_result) == [
        {"prompt": "first", "duration": 3},
        {"prompt": "second", "duration": 5},
    ]

    llm_node = class_mappings["BizyTRD_LLMToolConfig"]()
    assert json.loads(llm_node.execute(web_search=True)[0]) == ["web_search"]
    assert json.loads(llm_node.execute(web_search=False)[0]) == []
