"""テスト: LLMOps ユーティリティ."""

import pytest
from llmops.utils import hello_llmops, version_info


class TestBasicUtils:
    """基本ユーティリティのテスト."""

    def test_hello_llmops(self):
        """テスト: hello_llmops 関数."""
        result = hello_llmops()
        assert result == "Welcome to LLMOps Lab!"
        assert isinstance(result, str)

    def test_version_info(self):
        """テスト: version_info 関数."""
        result = version_info()
        assert "version" in result
        assert result["version"] == "0.1.0"
        assert "status" in result


class TestDataTypes:
    """データ型テスト."""

    def test_hello_llmops_returns_string(self):
        """戻り値が文字列型であることを確認."""
        result = hello_llmops()
        assert isinstance(result, str)

    def test_version_info_returns_dict(self):
        """戻り値が辞書型であることを確認."""
        result = version_info()
        assert isinstance(result, dict)


# テストが正常に実行される確認用
@pytest.mark.parametrize(
    "input_val,expected",
    [
        ("test1", "test1"),
        ("test2", "test2"),
    ],
)
def test_parametrized_example(input_val, expected):
    """パラメータ化テストの例."""
    assert input_val == expected
