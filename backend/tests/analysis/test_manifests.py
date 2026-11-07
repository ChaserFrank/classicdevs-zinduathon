import pytest

from apps.analysis.services import manifests as m


def test_package_json_all_sections():
    text = '{"dependencies": {"React": "18"}, "devDependencies": {"jest": "29"}, "peerDependencies": {"vue": "3"}}'
    assert m.parse_package_json(text) == {"React", "jest", "vue"}


@pytest.mark.parametrize("text", ["", "not json", "[]", '{"dependencies": []}'])
def test_package_json_malformed(text):
    assert m.parse_package_json(text) == set()


def test_requirements():
    text = "# deps\nDjango>=5 ; python_version>'3'\nrequests[socks]==2\n-r base.txt\ngit+https://x\n\nnumpy  # math\n"
    assert m.parse_requirements(text) == {"Django", "requests", "numpy"}


def test_pyproject_pep621_poetry_and_groups():
    text = """
[project]
dependencies = ["fastapi>=0.1", "pydantic"]
[project.optional-dependencies]
db = ["psycopg[binary]"]
[dependency-groups]
dev = ["pytest", {include-group = "x"}]
[tool.poetry.dependencies]
python = "^3.12"
flask = "*"
[tool.poetry.group.dev.dependencies]
black = "*"
[tool.poetry.dev-dependencies]
mypy = "*"
"""
    assert m.parse_pyproject(text) == {
        "fastapi",
        "pydantic",
        "psycopg",
        "pytest",
        "flask",
        "black",
        "mypy",
    }


def test_pyproject_malformed():
    assert m.parse_pyproject("[[[") == set()


def test_go_mod():
    text = "module x\n\ngo 1.22\n\nrequire github.com/gin-gonic/gin v1.9.1\nrequire (\n\tgolang.org/x/net v0.1 // indirect\n\tgithub.com/lib/pq v1\n)\n"
    assert m.parse_go_mod(text) == {
        "github.com/gin-gonic/gin",
        "golang.org/x/net",
        "github.com/lib/pq",
    }


def test_pom():
    text = """<project xmlns="http://maven.apache.org/POM/4.0.0"><artifactId>app</artifactId>
    <dependencies><dependency><groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId></dependency></dependencies></project>"""
    assert m.parse_pom(text) == {"app", "spring-boot-starter-web"}


def test_pom_malformed():
    assert m.parse_pom("<project>") == set()


def test_dependencies_normalises_and_groups_by_ecosystem():
    result = m.dependencies(
        {
            "requirements.txt": "Django_REST.framework\n",
            "web/package.json": '{"dependencies": {"React": "18"}}',
            "README.md": "ignored",
        }
    )
    assert result == {"pypi": {"django-rest-framework"}, "npm": {"react"}}


@pytest.mark.parametrize(
    ("eco", "raw", "out"),
    [("pypi", "Psycopg2_Binary", "psycopg2-binary"), ("npm", " @Nestjs/Core ", "@nestjs/core")],
)
def test_normalise_package(eco, raw, out):
    assert m.normalise_package(eco, raw) == out
