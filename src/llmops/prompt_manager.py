"""Prompt management with versioning support.

Design:
- Load prompts from YAML files
- Support multiple prompt versions
- Template variable substitution
- Metadata tracking (version, created_at, tags)
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class PromptTemplate:
    """Represents a prompt template with metadata."""

    def __init__(
        self,
        version: str,
        system_prompt: str,
        user_prompt_template: str,
        description: str = "",
        tags: Optional[list[str]] = None,
        created_at: str = "",
        examples: Optional[list[Dict[str, str]]] = None,
    ):
        """Initialize prompt template.

        Args:
            version: Template version (e.g., "1.0", "2.0")
            system_prompt: System-level instructions
            user_prompt_template: User message template with {instruction} placeholder
            description: Short description of the prompt
            tags: List of tags for categorization
            created_at: ISO format timestamp
            examples: List of example usage cases
        """
        self.version = version
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template
        self.description = description
        self.tags = tags or []
        self.created_at = created_at
        self.examples = examples or []

    def render(self, instruction: str) -> str:
        """Render user prompt with instruction.

        Args:
            instruction: User instruction to substitute

        Returns:
            Rendered user prompt
        """
        return self.user_prompt_template.format(instruction=instruction)

    def __repr__(self) -> str:
        return f"<PromptTemplate v{self.version} - {self.description}>"


class PromptManager:
    """Manages prompt templates and versions."""

    def __init__(self, prompts_dir: str = "prompts"):
        """Initialize prompt manager.

        Args:
            prompts_dir: Directory containing prompt YAML files
        """
        self.prompts_dir = Path(prompts_dir)
        self.templates: Dict[str, PromptTemplate] = {}
        self._load_all_prompts()

    def _load_all_prompts(self) -> None:
        """Load all prompt templates from directory."""
        if not self.prompts_dir.exists():
            logger.warning(f"Prompts directory not found: {self.prompts_dir}")
            return

        for yaml_file in sorted(self.prompts_dir.glob("*.yaml")):
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data:
                        template = PromptTemplate(
                            version=data.get("version", "unknown"),
                            system_prompt=data.get("system_prompt", ""),
                            user_prompt_template=data.get("user_prompt_template", ""),
                            description=data.get("description", ""),
                            tags=data.get("tags", []),
                            created_at=data.get("created_at", ""),
                            examples=data.get("examples", []),
                        )
                        self.templates[template.version] = template
                        logger.info(f"Loaded prompt template: {template}")
            except Exception as e:
                logger.error(f"Failed to load prompt {yaml_file}: {e}")

    def get(self, version: str) -> Optional[PromptTemplate]:
        """Get prompt template by version.

        Args:
            version: Template version (e.g., "1.0")

        Returns:
            PromptTemplate if found, None otherwise
        """
        return self.templates.get(version)

    def get_latest(self) -> Optional[PromptTemplate]:
        """Get latest prompt template by semantic versioning.

        Returns:
            Latest PromptTemplate if any exist
        """
        if not self.templates:
            return None

        # Sort versions numerically
        sorted_versions = sorted(
            self.templates.keys(),
            key=lambda v: tuple(map(int, v.split("."))),
            reverse=True,
        )
        return self.templates[sorted_versions[0]]

    def list_versions(self) -> list[str]:
        """List all available prompt versions.

        Returns:
            List of version strings, sorted
        """
        return sorted(
            self.templates.keys(),
            key=lambda v: tuple(map(int, v.split("."))),
            reverse=True,
        )

    def get_info(self, version: str) -> Dict[str, Any]:
        """Get metadata about a prompt version.

        Args:
            version: Template version

        Returns:
            Dictionary with prompt metadata
        """
        template = self.get(version)
        if not template:
            return {}

        return {
            "version": template.version,
            "description": template.description,
            "tags": template.tags,
            "created_at": template.created_at,
            "example_count": len(template.examples),
        }
