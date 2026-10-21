import pytest

from services.profiling.manifests import Dependency, is_manifest, parse_manifest


def names(filename: str, text: str) -> list[str]:
    return [d.name for d in parse_manifest(filename, text)]


def test_requirements_txt() -> None:
    text = """
# comment
Django>=5.2,<6
djangorestframework==3.16  # inline comment
celery[redis]>=5.5
psycopg2_binary ; python_version >= "3.10"
-r dev.txt
-e git+https://github.com/x/y.git#egg=y
https://example.com/pkg.whl
./local/path
"""
    assert names("requirements.txt", text) == [
        "celery",
        "django",
        "djangorestframework",
        "psycopg2-binary",
    ]
    assert parse_manifest("requirements.txt", "flask")[0] == Dependency("pypi", "flask")


def test_pyproject_pep621_groups_and_poetry() -> None:
    text = """
[project]
dependencies = ["fastapi>=0.110", "pydantic[email]"]
[project.optional-dependencies]
db = ["SQLAlchemy"]
[dependency-groups]
dev = ["pytest>=8", {include-group = "lint"}]
[tool.poetry.dependencies]
python = "^3.12"
httpx = "*"
[tool.poetry.group.test.dependencies]
respx = "*"
"""
    assert names("pyproject.toml", text) == [
        "fastapi",
        "httpx",
        "pydantic",
        "pytest",
        "respx",
        "sqlalchemy",
    ]


def test_package_json() -> None:
    text = (
        '{"dependencies": {"react": "^19"}, "devDependencies": {"@types/node": "^24",'
        ' "vite": "^7"}, "peerDependencies": {"React-DOM": "*"}}'
    )
    assert names("package.json", text) == ["@types/node", "react", "react-dom", "vite"]


def test_go_mod() -> None:
    text = """module example.com/app

go 1.23

require github.com/gin-gonic/gin v1.10.0

require (
    github.com/jackc/pgx/v5 v5.7.1 // indirect
    // a comment line
    k8s.io/client-go v0.31.0
)
"""
    assert names("go.mod", text) == [
        "github.com/gin-gonic/gin",
        "github.com/jackc/pgx/v5",
        "k8s.io/client-go",
    ]


def test_cargo_toml() -> None:
    text = """
[dependencies]
tokio = { version = "1", features = ["full"] }
serde = "1"
pg = { package = "tokio-postgres", version = "0.7" }
[dev-dependencies]
criterion = "0.5"
[workspace.dependencies]
axum = "0.8"
"""
    assert names("Cargo.toml", text) == ["axum", "criterion", "serde", "tokio", "tokio-postgres"]


def test_pom_xml() -> None:
    text = """<project><dependencies>
  <dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId>
  </dependency>
  <dependency><groupId>org.postgresql</groupId><artifactId>postgresql</artifactId>
  <version>42</version></dependency>
</dependencies></project>"""
    assert names("pom.xml", text) == [
        "org.postgresql:postgresql",
        "org.springframework.boot:spring-boot-starter-web",
    ]


@pytest.mark.parametrize("filename", ["build.gradle", "build.gradle.kts"])
def test_gradle(filename: str) -> None:
    text = """dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    testImplementation 'org.junit.jupiter:junit-jupiter:5.10.0'
    implementation(platform("software.amazon.awssdk:bom:2.25.0"))
    implementation project(':core')
}"""
    assert names(filename, text) == [
        "org.junit.jupiter:junit-jupiter",
        "org.springframework.boot:spring-boot-starter-web",
        "software.amazon.awssdk:bom",
    ]


@pytest.mark.parametrize(
    ("filename", "text"),
    [
        ("package.json", "{not json"),
        ("package.json", "[1, 2]"),
        ("pyproject.toml", "[project\ndependencies = "),
        ("Cargo.toml", "= broken"),
    ],
)
def test_malformed_manifest_returns_nothing(filename: str, text: str) -> None:
    assert parse_manifest(filename, text) == []


def test_unsupported_file() -> None:
    assert not is_manifest("setup.py")
    assert parse_manifest("setup.py", "install_requires=['django']") == []


DEEP = 100_000
DEEP_PACKAGE_JSON = '{"dependencies": ' + "[" * DEEP + "]" * DEEP + "}"


@pytest.mark.parametrize(
    ("filename", "text"),
    [
        ("package.json", DEEP_PACKAGE_JSON),
        ("pyproject.toml", "x = " + "[" * DEEP + "]" * DEEP + "\n"),
        ("Cargo.toml", "x = " + "[" * DEEP + "]" * DEEP + "\n"),
    ],
    ids=["package.json", "pyproject.toml", "Cargo.toml"],  # the texts are too long for ids
)
def test_deeply_nested_manifest_yields_nothing(filename: str, text: str) -> None:
    assert parse_manifest(filename, text) == []
