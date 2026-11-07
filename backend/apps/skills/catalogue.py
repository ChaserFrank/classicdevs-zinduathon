"""Seed data for the skill catalogue (brief section 8.2), used by the data migration and tests.

Format: skill name → (category, aliases, {ecosystem: [packages]}). GitHub language names that
differ from the skill name are listed as aliases (lowercase), e.g. "jupyter notebook" → Python.
"""

SEED: dict[str, tuple[str, list[str], dict[str, list[str]]]] = {
    # Languages (GitHub's language names, lowercase, are aliases)
    "Python": ("language", ["py", "python3", "jupyter notebook"], {}),
    "JavaScript": ("language", ["js", "ecmascript"], {}),
    "TypeScript": ("language", ["ts"], {}),
    "Java": ("language", [], {}),
    "Kotlin": ("language", [], {}),
    "Go": ("language", ["golang"], {}),
    "C": ("language", [], {}),
    "C++": ("language", ["cpp"], {}),
    "C#": ("language", ["csharp", "c sharp"], {}),
    "PHP": ("language", [], {}),
    "Ruby": ("language", [], {}),
    "Rust": ("language", [], {}),
    "Swift": ("language", [], {}),
    "Dart": ("language", [], {}),
    "R": ("language", [], {}),
    "HTML": ("language", ["html5"], {}),
    "CSS": ("language", ["css3", "scss", "sass", "less"], {}),
    "Shell": ("language", ["bash", "powershell"], {}),
    "SQL": ("language", ["plpgsql", "tsql", "plsql"], {}),
    # Frameworks
    "React": ("framework", ["reactjs", "react.js"], {"npm": ["react"]}),
    "Next.js": ("framework", ["nextjs", "next"], {"npm": ["next"]}),
    "Vue.js": ("framework", ["vue", "vuejs"], {"npm": ["vue"]}),
    "Angular": ("framework", ["angularjs"], {"npm": ["@angular/core"]}),
    "Express": ("framework", ["express.js", "expressjs"], {"npm": ["express"]}),
    "NestJS": ("framework", ["nest", "nest.js"], {"npm": ["@nestjs/core"]}),
    "Django": ("framework", [], {"pypi": ["django"]}),
    "Django REST Framework": (
        "framework",
        ["drf", "django rest"],
        {"pypi": ["djangorestframework"]},
    ),
    "Flask": ("framework", [], {"pypi": ["flask"]}),
    "FastAPI": ("framework", [], {"pypi": ["fastapi"]}),
    "Tailwind CSS": ("framework", ["tailwind", "tailwindcss"], {"npm": ["tailwindcss"]}),
    "Spring Boot": (
        "framework",
        ["spring"],
        {"maven": ["spring-boot-starter", "spring-boot-starter-web"]},
    ),
    "Gin": ("framework", [], {"go": ["github.com/gin-gonic/gin"]}),
    # Practices
    "Testing": (
        "practice",
        ["unit testing", "tdd", "automated testing"],
        {"npm": ["jest", "vitest"], "pypi": ["pytest"]},
    ),
    "CI/CD": ("practice", ["ci", "cicd", "github actions", "continuous integration"], {}),
    "Data analysis": (
        "practice",
        ["data science", "pandas", "numpy"],
        {"pypi": ["pandas", "numpy"]},
    ),
    "Machine learning": (
        "practice",
        ["ml", "deep learning", "ai"],
        {"pypi": ["scikit-learn", "torch", "tensorflow"]},
    ),
    # Tools
    "Node.js": ("tool", ["node", "nodejs"], {}),
    "PostgreSQL": (
        "tool",
        ["postgres", "psql"],
        {"npm": ["pg", "prisma"], "pypi": ["psycopg", "psycopg2", "psycopg2-binary"]},
    ),
    "MongoDB": ("tool", ["mongo"], {"npm": ["mongoose"], "pypi": ["pymongo"]}),
    "Docker": ("tool", ["docker compose", "containers"], {}),
}

# Skills implied by another skill's evidence (brief: Express or NestJS also implies Node.js).
IMPLIES: dict[str, list[str]] = {"Express": ["Node.js"], "NestJS": ["Node.js"]}

# Practice skills detected from the file tree rather than languages or manifests.
TESTING, CI_CD, DOCKER = "Testing", "CI/CD", "Docker"
