"""Static repository understanding without running project code."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MANIFEST_PATTERNS = {
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "setup.py": "python",
    "package.json": "node",
    "pom.xml": "java",
    "build.gradle": "java",
    "Cargo.toml": "rust",
    "go.mod": "go",
}

ENTRY_CANDIDATES = [
    "app/main.py",
    "main.py",
    "src/main.py",
    "app.py",
    "server.py",
    "manage.py",
    "src/app.py",
    "pages/index.tsx",
    "app/page.tsx",
    "src/index.ts",
    "index.ts",
    "lib/main.dart",
]


@dataclass(slots=True)
class RepositoryContext:
    """Summary of project type, framework, commands and dependency signals."""

    root: Path
    language: str | None = None
    framework: str | None = None
    dependency_manager: str | None = None
    entrypoint: str | None = None
    test_command: str | None = None
    dependencies: list[str] = field(default_factory=list)
    manifests: list[str] = field(default_factory=list)
    readme: str | None = None
    test_directories: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "language": self.language,
            "framework": self.framework,
            "dependency_manager": self.dependency_manager,
            "entrypoint": self.entrypoint,
            "test_command": self.test_command,
            "dependencies": self.dependencies,
            "manifests": self.manifests,
            "readme": self.readme,
            "test_directories": self.test_directories,
            "summary": self.summary,
        }


class RepositoryAnalyzer:
    """Detect repository characteristics by inspecting safe surface files."""

    def analyze(self, root: str | Path) -> RepositoryContext:
        root_path = Path(root).resolve()
        if not root_path.is_dir():
            raise FileNotFoundError(f"Workspace directory not found: {root_path}")
        manifests = self._find_manifests(root_path)
        language = None
        manager = None
        dependencies: list[str] = []
        for manifest in manifests:
            lang = MANIFEST_PATTERNS.get(manifest)
            if lang:
                language = language or lang
        if "pyproject.toml" in manifests:
            manager = "uv" if (root_path / "uv.lock").exists() else "pip"
            dependencies = self._parse_python_pyproject(root_path / "pyproject.toml")
        elif "package.json" in manifests:
            manager = "npm"
            dependencies = self._parse_package_json(root_path / "package.json")
        elif "requirements.txt" in manifests:
            manager = "pip"
            dependencies = self._parse_requirements(root_path / "requirements.txt")

        framework = self._detect_framework(root_path, dependencies)
        entrypoint = self._find_entrypoint(root_path)
        test_command = self._detect_test_command(root_path, manager, framework)
        readme = self._find_readme(root_path)
        test_dirs = self._find_test_directories(root_path)
        summary = self._build_summary(
            language=language,
            framework=framework,
            entrypoint=entrypoint,
            test_command=test_command,
            manifests=manifests,
            readme=readme,
        )
        return RepositoryContext(
            root=root_path,
            language=language,
            framework=framework,
            dependency_manager=manager,
            entrypoint=entrypoint,
            test_command=test_command,
            dependencies=sorted(set(dependencies)),
            manifests=manifests,
            readme=readme,
            test_directories=test_dirs,
            summary=summary,
        )

    @staticmethod
    def _find_manifests(root: Path) -> list[str]:
        files = []
        for name in MANIFEST_PATTERNS:
            if (root / name).is_file():
                files.append(name)
        return files

    @staticmethod
    def _parse_python_pyproject(path: Path) -> list[str]:
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError):
            return []
        project = data.get("project", {})
        if isinstance(project, dict):
            raw = project.get("dependencies", [])
            if isinstance(raw, list):
                return [str(item).split("[")[0].split(">=")[0].strip() for item in raw]
        return []

    @staticmethod
    def _parse_package_json(path: Path) -> list[str]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        deps = data.get("dependencies", {})
        return [str(name) for name in deps]

    @staticmethod
    def _parse_requirements(path: Path) -> list[str]:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        return [
            line.split("==")[0].split(">=")[0].split("<")[0].strip()
            for line in lines
            if line.strip() and not line.startswith("#")
        ]

    @staticmethod
    def _detect_framework(root: Path, dependencies: list[str]) -> str | None:
        deps_lower = {dep.lower() for dep in dependencies}
        if "fastapi" in deps_lower:
            return "FastAPI"
        if "flask" in deps_lower or (root / "app.py").exists() or (root / "server.py").exists():
            return "Flask" if "flask" in deps_lower else "Python web"
        if "django" in deps_lower:
            return "Django"
        if "next" in deps_lower or "next.js" in deps_lower:
            return "Next.js"
        if "react" in deps_lower:
            return "React"
        if (root / "src" / "main.py").exists() and any(path.name == "pyproject.toml" for path in root.iterdir()):
            return "Python"
        return None

    @staticmethod
    def _find_entrypoint(root: Path) -> str | None:
        for candidate in ENTRY_CANDIDATES:
            if (root / candidate).is_file():
                return candidate
        return None

    @staticmethod
    def _detect_test_command(root: Path, manager: str | None, framework: str | None) -> str | None:
        if (root / "pyproject.toml").is_file():
            return "uv run pytest -q" if (root / "uv.lock").exists() else "python -m pytest -q"
        if (root / "pytest.ini").exists() or (root / "conftest.py").exists():
            return "pytest"
        package_json = root / "package.json"
        if package_json.is_file():
            try:
                data = json.loads(package_json.read_text(encoding="utf-8"))
                test = data.get("scripts", {}).get("test")
                if test:
                    return f"npm test -- {test}" if str(test).startswith("next") else f"npm run test -- {test}"
            except (OSError, ValueError):
                return None
            return "npm test"
        if manager == "npm":
            return "npm test"
        return "pytest" if framework == "Python" else None

    @staticmethod
    def _find_readme(root: Path) -> str | None:
        for candidate in ("README.md", "README", "readme.md", "README.zh-CN.md"):
            if (root / candidate).is_file():
                return candidate
        return None

    @staticmethod
    def _find_test_directories(root: Path) -> list[str]:
        directories = []
        for candidate in ("tests", "test", "__tests__"):
            if (root / candidate).is_dir():
                directories.append(candidate)
        return directories

    @staticmethod
    def _build_summary(
        *,
        language: str | None,
        framework: str | None,
        entrypoint: str | None,
        test_command: str | None,
        manifests: list[str],
        readme: str | None,
    ) -> str:
        parts = []
        if language:
            parts.append(f"{language} project")
        if framework:
            parts.append(f"framework: {framework}")
        if entrypoint:
            parts.append(f"entrypoint: {entrypoint}")
        if test_command:
            parts.append(f"tests: {test_command}")
        if readme:
            parts.append(f"readme: {readme}")
        parts.append(f"manifests: {', '.join(manifests) or 'none'}")
        return ". ".join(parts) + "."
