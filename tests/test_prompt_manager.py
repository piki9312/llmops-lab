"""Tests for prompt versioning and management."""

import pytest
from pathlib import Path

from llmops.prompt_manager import PromptTemplate, PromptManager


class TestPromptTemplate:
    """Test PromptTemplate class."""

    def test_template_initialization(self):
        """Test template creation with metadata."""
        template = PromptTemplate(
            version="1.0",
            system_prompt="You are helpful.",
            user_prompt_template="Answer: {instruction}",
            description="Basic template",
            tags=["basic", "v1"],
        )
        assert template.version == "1.0"
        assert template.description == "Basic template"
        assert "basic" in template.tags

    def test_template_render(self):
        """Test rendering with variable substitution."""
        template = PromptTemplate(
            version="1.0",
            system_prompt="System",
            user_prompt_template="User instruction: {instruction}",
        )
        rendered = template.render("Do something")
        assert "Do something" in rendered
        assert rendered == "User instruction: Do something"

    def test_template_repr(self):
        """Test string representation."""
        template = PromptTemplate(
            version="2.0",
            system_prompt="System",
            user_prompt_template="Template",
            description="Test template",
        )
        repr_str = repr(template)
        assert "2.0" in repr_str
        assert "Test template" in repr_str


class TestPromptManager:
    """Test PromptManager class."""

    def test_load_prompts_from_directory(self):
        """Test loading prompt templates from directory."""
        prompts_dir = Path(__file__).parent.parent / "prompts"
        manager = PromptManager(str(prompts_dir))

        # Should load v1, v2, v3
        versions = manager.list_versions()
        assert len(versions) >= 3
        assert "1.0" in versions
        assert "2.0" in versions
        assert "3.0" in versions

    def test_get_specific_version(self):
        """Test retrieving specific prompt version."""
        prompts_dir = Path(__file__).parent.parent / "prompts"
        manager = PromptManager(str(prompts_dir))

        template = manager.get("1.0")
        assert template is not None
        assert template.version == "1.0"
        assert "system_prompt" in dir(template)
        assert template.system_prompt != ""

    def test_get_nonexistent_version(self):
        """Test getting version that doesn't exist."""
        prompts_dir = Path(__file__).parent.parent / "prompts"
        manager = PromptManager(str(prompts_dir))

        template = manager.get("99.0")
        assert template is None

    def test_get_latest_version(self):
        """Test getting latest prompt by semantic versioning."""
        prompts_dir = Path(__file__).parent.parent / "prompts"
        manager = PromptManager(str(prompts_dir))

        latest = manager.get_latest()
        assert latest is not None
        # Should be 3.0 if all three templates exist
        assert latest.version == "3.0"

    def test_list_versions_sorted(self):
        """Test that versions are sorted correctly."""
        prompts_dir = Path(__file__).parent.parent / "prompts"
        manager = PromptManager(str(prompts_dir))

        versions = manager.list_versions()
        # Should be in descending order (latest first)
        assert versions[0] == "3.0"
        assert versions[-1] == "1.0"

    def test_get_info(self):
        """Test retrieving prompt metadata."""
        prompts_dir = Path(__file__).parent.parent / "prompts"
        manager = PromptManager(str(prompts_dir))

        info = manager.get_info("1.0")
        assert info["version"] == "1.0"
        assert "description" in info
        assert "tags" in info
        assert "created_at" in info
        assert "example_count" in info

    def test_get_info_nonexistent(self):
        """Test getting info for nonexistent version."""
        prompts_dir = Path(__file__).parent.parent / "prompts"
        manager = PromptManager(str(prompts_dir))

        info = manager.get_info("99.0")
        assert info == {}

    def test_template_examples(self):
        """Test that templates have examples."""
        prompts_dir = Path(__file__).parent.parent / "prompts"
        manager = PromptManager(str(prompts_dir))

        template = manager.get("1.0")
        assert template is not None
        assert len(template.examples) > 0
        assert "instruction" in template.examples[0]

    def test_nonexistent_directory(self):
        """Test handling missing prompts directory."""
        manager = PromptManager("/nonexistent/path")
        versions = manager.list_versions()
        assert versions == []
