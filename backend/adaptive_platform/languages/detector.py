from __future__ import annotations

import re
from pathlib import PurePosixPath

from adaptive_platform.languages.models import FileLanguageDetection

EXTENSION_LANGUAGES: dict[str, str] = {
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cs": "C#",
    ".dart": "Dart",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".fs": "F#",
    ".fsx": "F#",
    ".go": "Go",
    ".h": "C",
    ".hpp": "C++",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".lua": "Lua",
    ".m": "Objective-C",
    ".php": "PHP",
    ".pl": "Perl",
    ".pm": "Perl",
    ".py": "Python",
    ".pyi": "Python",
    ".r": "R",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".scala": "Scala",
    ".sh": "Shell",
    ".swift": "Swift",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".vue": "Vue",
}

FILENAME_LANGUAGES: dict[str, str] = {
    "Rakefile": "Ruby",
    "Jenkinsfile": "Groovy",
}

SHEBANG_LANGUAGES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?:^|[/\s])python(?:[0-9.]*)?(?:\s|$)"), "Python"),
    (re.compile(r"(?:^|[/\s])(?:node|deno)(?:\s|$)"), "JavaScript"),
    (re.compile(r"(?:^|[/\s])(?:ba|z|k)?sh(?:\s|$)"), "Shell"),
    (re.compile(r"(?:^|[/\s])ruby(?:\s|$)"), "Ruby"),
    (re.compile(r"(?:^|[/\s])perl(?:\s|$)"), "Perl"),
    (re.compile(r"(?:^|[/\s])php(?:\s|$)"), "PHP"),
)

GENERATED_PARTS = frozenset({"generated", "gen", "autogen"})
VENDORED_PARTS = frozenset({"vendor", "vendors", "third_party", "third-party", "external"})


def detect_language(path: PurePosixPath, text: str | None = None) -> FileLanguageDetection:
    suffix = path.suffix.lower()
    if suffix in EXTENSION_LANGUAGES:
        return FileLanguageDetection(EXTENSION_LANGUAGES[suffix], f"extension:{suffix}")
    if path.name in FILENAME_LANGUAGES:
        return FileLanguageDetection(FILENAME_LANGUAGES[path.name], f"filename:{path.name}")
    if text and text.startswith("#!"):
        shebang = text.splitlines()[0][2:].strip()
        for pattern, language in SHEBANG_LANGUAGES:
            if pattern.search(shebang):
                return FileLanguageDetection(language, f"shebang:{language.lower()}")
    return FileLanguageDetection(None, None)


def is_generated_path(path: PurePosixPath) -> bool:
    lowered = {part.lower() for part in path.parts}
    return bool(lowered & GENERATED_PARTS) or path.name.endswith(".min.js")


def is_vendored_path(path: PurePosixPath) -> bool:
    return bool({part.lower() for part in path.parts} & VENDORED_PARTS)
