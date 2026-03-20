from pathlib import Path
from typing import Dict, Optional

import yaml

# Resolve skills dir relative to project root (parent of src/)
_LOADER_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _LOADER_DIR.parent
_DEFAULT_SKILLS_DIR = _PROJECT_ROOT / "skills"


class SkillRegistry:
    """
    Registry for discovering and loading skills from:
    - SKILL.md files (directory format: skills/<name>/SKILL.md)
    - .skill files (single-file format: skills/<name>.skill)
    - *.md files (markdown format: skills/<name>.md with YAML frontmatter)

    All formats use YAML frontmatter (name, description) and a markdown body.
    Only skills found in the configuration are available; no built-in fallbacks.
    """

    def __init__(self, skills_dir: Optional[str] = None):
        self.skills_dir = (
            Path(skills_dir) if skills_dir else _DEFAULT_SKILLS_DIR
        ).resolve()
        self.descriptions: Dict[str, str] = {}
        self._skill_paths: Dict[str, Path] = {}  # skill_name -> source file path
        self._cache: Dict[str, str] = {}

    def scan_skills(self) -> str:
        """
        Scan for available skills and return a formatted list.
        Only returns skills actually loaded from the configuration.

        Returns:
            Formatted string of skills for LLM context:
            "- skill_name: description\\n- skill_name2: description2"
        """
        self.descriptions.clear()
        self._skill_paths.clear()
        self._cache.clear()

        # Load from directory format: skills/<name>/SKILL.md
        for skill_path in self.skills_dir.rglob("SKILL.md"):
            self._parse_skill_metadata(skill_path, is_skill_file=False)

        # Load from single-file format: skills/<name>.skill
        for skill_path in self.skills_dir.rglob("*.skill"):
            if skill_path.is_file():
                self._parse_skill_metadata(skill_path, is_skill_file=True)

        # Load from markdown format: skills/<name>.md (skip README.md)
        for skill_path in self.skills_dir.glob("*.md"):
            if skill_path.is_file() and skill_path.name != "README.md":
                self._parse_skill_metadata(skill_path, is_skill_file=True)

        # Print available skills
        print(f"📚 Skills directory: {self.skills_dir}")
        if self.descriptions:
            print(f"📚 Available skills ({len(self.descriptions)}):")
            print(self.descriptions.keys())
            # for name in sorted(self.descriptions.keys()):
            #     print(f"   - {name}: {self.descriptions[name]}")
        else:
            print(f"⚠️  No skills found in {self.skills_dir}")

        return "\n".join(f"- {name}: {desc}" for name, desc in self.descriptions.items())

    def _parse_skill_metadata(self, path: Path, *, is_skill_file: bool = False) -> None:
        """Parse YAML frontmatter from a SKILL.md or .skill file."""
        name = path.stem if is_skill_file else path.parent.name
        desc = "No description"

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            parts = content.split("---", 2)

            if len(parts) >= 3:
                meta = yaml.safe_load(parts[1])
                if meta:
                    name = meta.get("name") or name
                    desc = meta.get("description", desc)
            elif is_skill_file:
                # Fallback: .skill file without frontmatter - use filename as name
                first_line = content.strip().split("\n")[0].lstrip("# ").strip()
                if first_line:
                    desc = first_line[:80]

            self.descriptions[name] = desc
            self._skill_paths[name] = path

        except Exception as e:
            print(f"Warning: Failed to parse skill at {path}: {e}")

    def load_skill_content(self, skill_name: str) -> Optional[str]:
        """
        Load the markdown body content for a specific skill, plus all resource files.
        Only loads skills that were discovered by scan_skills().

        Args:
            skill_name: Name of the skill to load

        Returns:
            The skill's instruction content (without frontmatter) with appended resource files, or None if not found
        """
        if skill_name in self._cache:
            return self._cache[skill_name]

        skill_path = self._skill_paths.get(skill_name)
        if skill_path is None:
            return None  # Only load skills discovered by scan_skills()

        try:
            content = skill_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"Warning: Failed to read skill at {skill_path}: {e}")
            return None

        parts = content.split("---", 2)
        body = parts[-1].strip() if len(parts) >= 3 else content.strip()

        # Load resource files from resources/ subdirectory (directory format only)
        resources_dir = skill_path.parent / "resources"
        if resources_dir.exists() and resources_dir.is_dir():
            for resource_file in sorted(resources_dir.iterdir()):
                if resource_file.is_file() and resource_file.suffix in {
                    ".c", ".h", ".ino", ".py", ".cpp", ".hpp"
                }:
                    try:
                        resource_content = resource_file.read_text(
                            encoding="utf-8", errors="replace"
                        )
                        body += f"\n\n--- Resource: {resource_file.name} ---\n{resource_content}"
                    except Exception as e:
                        print(f"Warning: Failed to load resource {resource_file}: {e}")

        self._cache[skill_name] = body

        return body

    def get_combined_skill_content(self, skill_names: list[str]) -> str:
        """
        Load and combine content from multiple skills.

        Args:
            skill_names: List of skill names to load

        Returns:
            Combined skill content with headers
        """
        sections = []

        for name in skill_names:
            content = self.load_skill_content(name)
            if content:
                sections.append(f"=== SKILL: {name} ===\n{content}")

        return "\n\n".join(sections)