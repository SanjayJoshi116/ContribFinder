"""Canonical skill and interest catalog (design D2).

The catalog in this module is the source of truth; ``developers.Skill`` / ``Interest`` rows are
upserted from it during analysis. Bump ``TAXONOMY_VERSION`` on any edit and run
``manage.py reanalyze_profiles``.

Matching vocabulary per skill:
- ``aliases``: phrases matched anywhere in README text (word boundaries, case-insensitive).
- ``ambiguous``: phrases that are also common words ("Go", "Rust", "Spring"). Matched only in
  README tech sections, badges and skill icons, never in free text.
- ``linguist``: GitHub language names (the repository languages API).
- ``topics``: extra GitHub topics; topics derived from the name and aliases are added.
- ``icons``: extra badge/icon tokens (shields.io ``logo=``, skillicons.dev, devicon).
- ``deps``: dependency names per ecosystem; a trailing ``*`` is a prefix match. The ``jvm``
  key applies to both Maven and Gradle (``group:artifact``).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from urllib.parse import unquote

TAXONOMY_VERSION = "2026.11.1"

LANGUAGE = "language"
FRAMEWORK = "framework"
LIBRARY = "library"
DATABASE = "database"
CLOUD = "cloud"
DEVOPS = "devops"
TOOL = "tool"

JVM_ECOSYSTEMS = ("maven", "gradle")
# Markup "languages": they inflate byte counts and say little about programming skill.
MARKUP = frozenset({"html", "css"})


@dataclass(frozen=True)
class SkillDef:
    slug: str
    name: str
    category: str
    aliases: tuple[str, ...] = ()
    ambiguous: tuple[str, ...] = ()
    linguist: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    icons: tuple[str, ...] = ()
    deps: dict[str, tuple[str, ...]] = field(default_factory=dict)
    implies_interests: tuple[str, ...] = ()


@dataclass(frozen=True)
class InterestDef:
    slug: str
    name: str
    synonyms: tuple[str, ...]
    topics: tuple[str, ...]


def _s(
    slug: str,
    name: str,
    category: str,
    *,
    aliases: Iterable[str] = (),
    ambiguous: Iterable[str] = (),
    linguist: Iterable[str] = (),
    topics: Iterable[str] = (),
    icons: Iterable[str] = (),
    pypi: Iterable[str] = (),
    npm: Iterable[str] = (),
    go: Iterable[str] = (),
    cargo: Iterable[str] = (),
    jvm: Iterable[str] = (),
    interests: Iterable[str] = (),
    name_is_ambiguous: bool = False,
) -> SkillDef:
    alias_list = list(aliases)
    ambiguous_list = list(ambiguous)
    (ambiguous_list if name_is_ambiguous else alias_list).insert(0, name.lower())
    deps = {
        eco: tuple(names)
        for eco, names in (
            ("pypi", pypi),
            ("npm", npm),
            ("go", go),
            ("cargo", cargo),
            ("jvm", jvm),
        )
        if names
    }
    return SkillDef(
        slug=slug,
        name=name,
        category=category,
        aliases=tuple(dict.fromkeys(a.lower() for a in alias_list)),
        ambiguous=tuple(dict.fromkeys(a.lower() for a in ambiguous_list)),
        linguist=tuple(linguist),
        topics=tuple(topics),
        icons=tuple(icons),
        deps=deps,
        implies_interests=tuple(interests),
    )


# fmt: off
SKILLS: tuple[SkillDef, ...] = (
    # --- languages -------------------------------------------------------------------
    _s("python", "Python", LANGUAGE, aliases=["python3"], linguist=["Python"], icons=["py"]),
    _s("javascript", "JavaScript", LANGUAGE, aliases=["js", "ecmascript", "es6"],
       linguist=["JavaScript"]),
    _s("typescript", "TypeScript", LANGUAGE, ambiguous=["ts"], linguist=["TypeScript"],
       npm=["typescript"]),
    _s("java", "Java", LANGUAGE, linguist=["Java"], icons=["openjdk"]),
    _s("kotlin", "Kotlin", LANGUAGE, linguist=["Kotlin"]),
    _s("go", "Go", LANGUAGE, aliases=["golang"], linguist=["Go"], name_is_ambiguous=True),
    _s("rust", "Rust", LANGUAGE, aliases=["rustlang"], linguist=["Rust"],
       name_is_ambiguous=True),
    _s("c", "C", LANGUAGE, linguist=["C"], name_is_ambiguous=True),
    _s("cpp", "C++", LANGUAGE, aliases=["cpp"], linguist=["C++"], topics=["cpp", "cplusplus"]),
    _s("csharp", "C#", LANGUAGE, aliases=["csharp"], linguist=["C#"], icons=["cs"]),
    _s("ruby", "Ruby", LANGUAGE, linguist=["Ruby"], name_is_ambiguous=True),
    _s("php", "PHP", LANGUAGE, linguist=["PHP"]),
    _s("swift", "Swift", LANGUAGE, linguist=["Swift"], name_is_ambiguous=True),
    _s("objective-c", "Objective-C", LANGUAGE, aliases=["objc"], linguist=["Objective-C"]),
    _s("scala", "Scala", LANGUAGE, linguist=["Scala"]),
    _s("elixir", "Elixir", LANGUAGE, linguist=["Elixir"], name_is_ambiguous=True),
    _s("erlang", "Erlang", LANGUAGE, linguist=["Erlang"]),
    _s("haskell", "Haskell", LANGUAGE, linguist=["Haskell"]),
    _s("clojure", "Clojure", LANGUAGE, linguist=["Clojure"]),
    _s("dart", "Dart", LANGUAGE, linguist=["Dart"], name_is_ambiguous=True),
    _s("lua", "Lua", LANGUAGE, linguist=["Lua"]),
    _s("r", "R", LANGUAGE, aliases=["rlang"], linguist=["R"], name_is_ambiguous=True),
    _s("julia", "Julia", LANGUAGE, aliases=["julialang"], linguist=["Julia"],
       name_is_ambiguous=True),
    _s("perl", "Perl", LANGUAGE, linguist=["Perl"]),
    _s("shell", "Shell", LANGUAGE, aliases=["shell scripting", "zsh"], ambiguous=["bash"],
       linguist=["Shell"], icons=["gnubash"], name_is_ambiguous=True),
    _s("powershell", "PowerShell", LANGUAGE, linguist=["PowerShell"]),
    _s("sql", "SQL", LANGUAGE, aliases=["plpgsql", "t-sql", "tsql"],
       linguist=["PLpgSQL", "TSQL", "PLSQL", "SQL"]),
    _s("html", "HTML", LANGUAGE, aliases=["html5"], linguist=["HTML"]),
    _s("css", "CSS", LANGUAGE, aliases=["css3"], linguist=["CSS"]),
    _s("zig", "Zig", LANGUAGE, linguist=["Zig"], name_is_ambiguous=True),
    _s("ocaml", "OCaml", LANGUAGE, linguist=["OCaml"]),
    _s("fsharp", "F#", LANGUAGE, aliases=["fsharp"], linguist=["F#"]),
    _s("groovy", "Groovy", LANGUAGE, linguist=["Groovy"], name_is_ambiguous=True),
    _s("solidity", "Solidity", LANGUAGE, linguist=["Solidity"], interests=["blockchain"],
       name_is_ambiguous=True),
    _s("assembly", "Assembly", LANGUAGE, aliases=["x86 assembly"], ambiguous=["asm"],
       linguist=["Assembly"], name_is_ambiguous=True),
    _s("matlab", "MATLAB", LANGUAGE, linguist=["MATLAB"]),
    _s("fortran", "Fortran", LANGUAGE, linguist=["Fortran"]),
    _s("elm", "Elm", LANGUAGE, linguist=["Elm"], name_is_ambiguous=True),
    _s("nim", "Nim", LANGUAGE, linguist=["Nim"], name_is_ambiguous=True),
    _s("crystal", "Crystal", LANGUAGE, linguist=["Crystal"], name_is_ambiguous=True),
    _s("gdscript", "GDScript", LANGUAGE, linguist=["GDScript"]),

    # --- frameworks --------------------------------------------------------------------
    _s("django", "Django", FRAMEWORK, pypi=["django"]),
    _s("django-rest-framework", "Django REST Framework", FRAMEWORK,
       aliases=["drf", "djangorestframework"], topics=["django-rest-framework"],
       pypi=["djangorestframework"]),
    _s("flask", "Flask", FRAMEWORK, pypi=["flask"], name_is_ambiguous=True),
    _s("fastapi", "FastAPI", FRAMEWORK, pypi=["fastapi"]),
    _s("streamlit", "Streamlit", FRAMEWORK, pypi=["streamlit"]),
    _s("nodejs", "Node.js", FRAMEWORK, aliases=["nodejs", "node js"], topics=["node"],
       npm=["@types/node"], ambiguous=["node"]),
    _s("express", "Express", FRAMEWORK, aliases=["express.js", "expressjs"], npm=["express"],
       name_is_ambiguous=True),
    _s("nestjs", "NestJS", FRAMEWORK, aliases=["nest.js"], npm=["@nestjs/*"]),
    _s("react", "React", FRAMEWORK, aliases=["reactjs", "react.js"], npm=["react"],
       name_is_ambiguous=True),
    _s("nextjs", "Next.js", FRAMEWORK, aliases=["nextjs"], npm=["next"]),
    _s("vue", "Vue.js", FRAMEWORK, aliases=["vue", "vuejs", "vue3"], linguist=["Vue"],
       npm=["vue"]),
    _s("nuxt", "Nuxt", FRAMEWORK, aliases=["nuxt.js", "nuxtjs"], npm=["nuxt"]),
    _s("angular", "Angular", FRAMEWORK, aliases=["angularjs"], npm=["@angular/core"]),
    _s("svelte", "Svelte", FRAMEWORK, aliases=["sveltekit"], linguist=["Svelte"],
       npm=["svelte", "@sveltejs/kit"]),
    _s("astro", "Astro", FRAMEWORK, npm=["astro"], name_is_ambiguous=True),
    _s("react-native", "React Native", FRAMEWORK, npm=["react-native"],
       interests=["mobile-development"]),
    _s("electron", "Electron", FRAMEWORK, npm=["electron"], name_is_ambiguous=True),
    _s("tauri", "Tauri", FRAMEWORK, npm=["@tauri-apps/api"], cargo=["tauri"]),
    _s("spring", "Spring", FRAMEWORK, aliases=["spring boot", "springboot", "spring framework"],
       topics=["spring-boot"], jvm=["org.springframework.boot:*", "org.springframework:*"],
       name_is_ambiguous=True),
    _s("rails", "Ruby on Rails", FRAMEWORK, aliases=["rubyonrails"],
       ambiguous=["rails", "ror"], topics=["rails"]),
    _s("laravel", "Laravel", FRAMEWORK),
    _s("symfony", "Symfony", FRAMEWORK),
    _s("dotnet", ".NET", FRAMEWORK, aliases=["dotnet", "asp.net", "asp.net core",
       "dotnet core"], topics=["dotnet", "aspnetcore", "aspnet-core"]),
    _s("gin", "Gin", FRAMEWORK, go=["github.com/gin-gonic/gin"], name_is_ambiguous=True,
       topics=["gin-gonic"]),
    _s("actix", "Actix", FRAMEWORK, aliases=["actix-web"], cargo=["actix-web", "actix"]),
    _s("axum", "Axum", FRAMEWORK, cargo=["axum"]),
    _s("flutter", "Flutter", FRAMEWORK, interests=["mobile-development"],
       name_is_ambiguous=True),
    _s("swiftui", "SwiftUI", FRAMEWORK, interests=["mobile-development"]),
    _s("qt", "Qt", FRAMEWORK, aliases=["pyqt", "pyside"], pypi=["pyqt5", "pyqt6", "pyside6"],
       name_is_ambiguous=True),
    _s("tailwindcss", "Tailwind CSS", FRAMEWORK, aliases=["tailwind", "tailwindcss"],
       npm=["tailwindcss", "@tailwindcss/*"]),
    _s("bootstrap", "Bootstrap", FRAMEWORK, npm=["bootstrap"], name_is_ambiguous=True),
    _s("phoenix", "Phoenix", FRAMEWORK, name_is_ambiguous=True),
    _s("unity", "Unity", FRAMEWORK, aliases=["unity3d"], topics=["unity3d"],
       name_is_ambiguous=True, interests=["game-development"]),
    _s("unreal-engine", "Unreal Engine", FRAMEWORK, aliases=["ue5", "ue4"], ambiguous=["unreal"],
       icons=["unrealengine"], interests=["game-development"]),
    _s("godot", "Godot", FRAMEWORK, aliases=["godot engine"], icons=["godotengine"],
       interests=["game-development"]),

    # --- libraries -----------------------------------------------------------------------
    _s("numpy", "NumPy", LIBRARY, pypi=["numpy"]),
    _s("pandas", "pandas", LIBRARY, pypi=["pandas"], interests=["data-engineering"],
       name_is_ambiguous=True),
    _s("polars", "Polars", LIBRARY, pypi=["polars"], cargo=["polars"]),
    _s("scipy", "SciPy", LIBRARY, pypi=["scipy"], interests=["scientific-computing"]),
    _s("scikit-learn", "scikit-learn", LIBRARY, aliases=["sklearn", "scikit learn"],
       icons=["scikitlearn"], pypi=["scikit-learn"], interests=["ai-ml"]),
    _s("pytorch", "PyTorch", LIBRARY, ambiguous=["torch"], pypi=["torch"], interests=["ai-ml"]),
    _s("tensorflow", "TensorFlow", LIBRARY, pypi=["tensorflow", "tensorflow-*"],
       npm=["@tensorflow/tfjs"], interests=["ai-ml"]),
    _s("keras", "Keras", LIBRARY, pypi=["keras"], interests=["ai-ml"]),
    _s("hugging-face", "Hugging Face Transformers", LIBRARY,
       aliases=["hugging face", "huggingface"], topics=["transformers"],
       pypi=["transformers", "datasets", "huggingface-hub"], interests=["ai-ml"]),
    _s("langchain", "LangChain", LIBRARY, pypi=["langchain", "langchain-*"],
       npm=["langchain", "@langchain/*"], interests=["ai-ml"]),
    _s("openai-sdk", "OpenAI API", LIBRARY, aliases=["openai api"], pypi=["openai"],
       npm=["openai"], interests=["ai-ml"]),
    _s("xgboost", "XGBoost", LIBRARY, pypi=["xgboost"], interests=["ai-ml"]),
    _s("opencv", "OpenCV", LIBRARY, pypi=["opencv-python", "opencv-python-headless",
       "opencv-contrib-python"], interests=["ai-ml"]),
    _s("matplotlib", "Matplotlib", LIBRARY, pypi=["matplotlib"]),
    _s("jupyter", "Jupyter", TOOL, aliases=["jupyter notebook", "jupyterlab", "ipython"],
       linguist=["Jupyter Notebook"], pypi=["jupyter", "jupyterlab", "notebook"]),
    _s("pydantic", "Pydantic", LIBRARY, pypi=["pydantic"]),
    _s("sqlalchemy", "SQLAlchemy", LIBRARY, pypi=["sqlalchemy"]),
    _s("celery", "Celery", LIBRARY, pypi=["celery"], name_is_ambiguous=True),
    _s("pytest", "pytest", LIBRARY, pypi=["pytest"]),
    _s("jest", "Jest", LIBRARY, npm=["jest"], name_is_ambiguous=True),
    _s("vitest", "Vitest", LIBRARY, npm=["vitest"]),
    _s("playwright", "Playwright", LIBRARY, pypi=["playwright", "pytest-playwright"],
       npm=["playwright", "@playwright/test"], name_is_ambiguous=True),
    _s("cypress", "Cypress", LIBRARY, npm=["cypress"], name_is_ambiguous=True),
    _s("selenium", "Selenium", LIBRARY, name_is_ambiguous=True, pypi=["selenium"],
       npm=["selenium-webdriver"],
       jvm=["org.seleniumhq.selenium:*"]),
    _s("junit", "JUnit", LIBRARY, jvm=["junit:junit", "org.junit.jupiter:*"]),
    _s("hibernate", "Hibernate", LIBRARY, name_is_ambiguous=True,
       jvm=["org.hibernate:*", "org.hibernate.orm:*"]),
    _s("tokio", "Tokio", LIBRARY, cargo=["tokio"], name_is_ambiguous=True),
    _s("serde", "Serde", LIBRARY, cargo=["serde", "serde_json"]),
    _s("redux", "Redux", LIBRARY, npm=["redux", "@reduxjs/toolkit", "react-redux"]),
    _s("jquery", "jQuery", LIBRARY, npm=["jquery"]),
    _s("threejs", "Three.js", LIBRARY, aliases=["threejs"], npm=["three"]),
    _s("d3", "D3.js", LIBRARY, aliases=["d3js"], npm=["d3"], ambiguous=["d3"]),
    _s("prisma", "Prisma", LIBRARY, npm=["prisma", "@prisma/client"],
       name_is_ambiguous=True),
    _s("mongoose", "Mongoose", LIBRARY, npm=["mongoose"], name_is_ambiguous=True),
    _s("socketio", "Socket.IO", LIBRARY, aliases=["socketio"],
       npm=["socket.io", "socket.io-client"], pypi=["python-socketio"]),
    _s("spark", "Apache Spark", LIBRARY, aliases=["pyspark", "apache spark"],
       ambiguous=["spark"], topics=["spark", "apache-spark"], pypi=["pyspark"],
       jvm=["org.apache.spark:*"], interests=["data-engineering"]),
    _s("airflow", "Apache Airflow", TOOL, aliases=["apache airflow"], ambiguous=["airflow"],
       icons=["apacheairflow"], pypi=["apache-airflow"], interests=["data-engineering"]),
    _s("dbt", "dbt", TOOL, pypi=["dbt-core"], interests=["data-engineering"]),
    _s("cuda", "CUDA", LIBRARY, linguist=["Cuda"], pypi=["cupy", "pycuda"]),

    # --- databases ------------------------------------------------------------------------
    _s("postgresql", "PostgreSQL", DATABASE, aliases=["postgres", "psql"],
       icons=["postgres"],
       pypi=["psycopg", "psycopg2", "psycopg2-binary", "psycopg-binary", "asyncpg"],
       npm=["pg", "postgres"], go=["github.com/lib/pq", "github.com/jackc/pgx*"],
       cargo=["tokio-postgres", "postgres"], jvm=["org.postgresql:postgresql"]),
    _s("mysql", "MySQL", DATABASE, pypi=["mysqlclient", "pymysql", "mysql-connector-python"],
       npm=["mysql", "mysql2"], go=["github.com/go-sql-driver/mysql"],
       jvm=["mysql:mysql-connector-java", "com.mysql:mysql-connector-j"]),
    _s("mariadb", "MariaDB", DATABASE, pypi=["mariadb"], npm=["mariadb"]),
    _s("sqlite", "SQLite", DATABASE, aliases=["sqlite3"], npm=["sqlite3", "better-sqlite3"],
       cargo=["rusqlite"], go=["github.com/mattn/go-sqlite3"]),
    _s("mongodb", "MongoDB", DATABASE, aliases=["mongo"], pypi=["pymongo", "motor"],
       npm=["mongodb"], go=["go.mongodb.org/mongo-driver"], cargo=["mongodb"]),
    _s("redis", "Redis", DATABASE, pypi=["redis"], npm=["redis", "ioredis"],
       go=["github.com/redis/go-redis*", "github.com/go-redis/redis*"], cargo=["redis"]),
    _s("elasticsearch", "Elasticsearch", DATABASE, aliases=["opensearch"],
       pypi=["elasticsearch"], npm=["@elastic/elasticsearch"]),
    _s("cassandra", "Cassandra", DATABASE, aliases=["apache cassandra"], name_is_ambiguous=True,
       pypi=["cassandra-driver"]),
    _s("dynamodb", "DynamoDB", DATABASE, icons=["amazondynamodb"]),
    _s("neo4j", "Neo4j", DATABASE, pypi=["neo4j"], npm=["neo4j-driver"]),
    _s("clickhouse", "ClickHouse", DATABASE, pypi=["clickhouse-driver", "clickhouse-connect"]),
    _s("sql-server", "SQL Server", DATABASE, aliases=["mssql", "microsoft sql server"],
       icons=["microsoftsqlserver"], pypi=["pyodbc", "pymssql"], npm=["mssql"]),
    _s("supabase", "Supabase", DATABASE, pypi=["supabase"], npm=["@supabase/supabase-js"]),
    _s("bigquery", "BigQuery", DATABASE, aliases=["google bigquery"],
       icons=["googlebigquery"], pypi=["google-cloud-bigquery"]),
    _s("snowflake", "Snowflake", DATABASE, pypi=["snowflake-connector-python"],
       name_is_ambiguous=True),

    # --- cloud ------------------------------------------------------------------------------
    _s("aws", "AWS", CLOUD, aliases=["amazon web services"],
       icons=["amazonaws", "amazonwebservices"],
       pypi=["boto3", "botocore", "aws-cdk-lib"], npm=["aws-sdk", "@aws-sdk/*", "aws-cdk-lib"],
       go=["github.com/aws/aws-sdk-go*"], jvm=["software.amazon.awssdk:*", "com.amazonaws:*"],
       interests=["infrastructure-cloud"]),
    _s("gcp", "Google Cloud", CLOUD, aliases=["gcp", "google cloud platform"],
       icons=["googlecloud"], pypi=["google-cloud-*"], npm=["@google-cloud/*"],
       go=["cloud.google.com/go*"], interests=["infrastructure-cloud"]),
    _s("azure", "Azure", CLOUD, aliases=["microsoft azure"], name_is_ambiguous=True,
       icons=["microsoftazure"],
       pypi=["azure-*"], npm=["@azure/*"], interests=["infrastructure-cloud"]),
    _s("firebase", "Firebase", CLOUD, pypi=["firebase-admin"],
       npm=["firebase", "firebase-admin"]),
    _s("heroku", "Heroku", CLOUD),
    _s("vercel", "Vercel", CLOUD, npm=["vercel"]),
    _s("netlify", "Netlify", CLOUD),
    _s("cloudflare", "Cloudflare", CLOUD, aliases=["cloudflare workers"],
       npm=["wrangler", "@cloudflare/*"]),
    _s("digitalocean", "DigitalOcean", CLOUD),

    # --- devops ------------------------------------------------------------------------------
    _s("docker", "Docker", DEVOPS, aliases=["dockerfile", "docker compose", "docker-compose"],
       linguist=["Dockerfile"], interests=["devops"]),
    _s("kubernetes", "Kubernetes", DEVOPS, aliases=["k8s"],
       go=["k8s.io/client-go", "k8s.io/api"], pypi=["kubernetes"], interests=["devops"]),
    _s("helm", "Helm", DEVOPS, name_is_ambiguous=True),
    _s("terraform", "Terraform", DEVOPS, linguist=["HCL"], interests=["infrastructure-cloud"]),
    _s("pulumi", "Pulumi", DEVOPS, pypi=["pulumi", "pulumi-*"], npm=["@pulumi/*"]),
    _s("ansible", "Ansible", DEVOPS, pypi=["ansible", "ansible-core"]),
    _s("github-actions", "GitHub Actions", DEVOPS, icons=["githubactions"],
       npm=["@actions/core"]),
    _s("gitlab-ci", "GitLab CI", DEVOPS, aliases=["gitlab ci/cd"], icons=["gitlab"]),
    _s("jenkins", "Jenkins", DEVOPS, name_is_ambiguous=True),
    _s("nginx", "Nginx", DEVOPS),
    _s("linux", "Linux", DEVOPS, icons=["ubuntu", "debian", "archlinux", "fedora"]),
    _s("prometheus", "Prometheus", DEVOPS, pypi=["prometheus-client"],
       go=["github.com/prometheus/client_golang"], name_is_ambiguous=True),
    _s("grafana", "Grafana", DEVOPS),
    _s("nix", "Nix", DEVOPS, aliases=["nixos"], linguist=["Nix"], name_is_ambiguous=True),

    # --- tools --------------------------------------------------------------------------------
    _s("git", "Git", TOOL, icons=["github"], name_is_ambiguous=True),
    _s("graphql", "GraphQL", TOOL, pypi=["graphene", "strawberry-graphql", "ariadne"],
       npm=["graphql", "@apollo/client", "@apollo/server", "apollo-server"],
       go=["github.com/99designs/gqlgen"]),
    _s("grpc", "gRPC", TOOL, pypi=["grpcio"], npm=["@grpc/grpc-js"],
       go=["google.golang.org/grpc"], cargo=["tonic"], jvm=["io.grpc:*"]),
    _s("kafka", "Apache Kafka", TOOL, aliases=["apache kafka"], ambiguous=["kafka"],
       icons=["apachekafka"], pypi=["kafka-python", "confluent-kafka", "aiokafka"],
       npm=["kafkajs"], jvm=["org.apache.kafka:*"], interests=["data-engineering"]),
    _s("rabbitmq", "RabbitMQ", TOOL, pypi=["pika", "aio-pika"], npm=["amqplib"]),
    _s("webpack", "webpack", TOOL, npm=["webpack"]),
    _s("vite", "Vite", TOOL, npm=["vite"], name_is_ambiguous=True),
    _s("sass", "Sass", TOOL, aliases=["scss"], linguist=["SCSS", "Sass"], npm=["sass"],
       name_is_ambiguous=True),
    _s("figma", "Figma", TOOL),
    _s("postman", "Postman", TOOL, name_is_ambiguous=True),
    _s("vim", "Vim", TOOL, aliases=["neovim", "nvim"], linguist=["Vim Script"],
       name_is_ambiguous=True),
    _s("webassembly", "WebAssembly", TOOL, aliases=["wasm"], linguist=["WebAssembly"],
       cargo=["wasm-bindgen"]),
    _s("openapi", "OpenAPI", TOOL, aliases=["swagger"], icons=["openapiinitiative"],
       pypi=["drf-spectacular", "drf-yasg"], npm=["swagger-ui-express"]),
    _s("eslint", "ESLint", TOOL, npm=["eslint"]),
    _s("storybook", "Storybook", TOOL, npm=["storybook", "@storybook/*"],
       name_is_ambiguous=True),
    _s("deno", "Deno", TOOL, name_is_ambiguous=True),
    _s("bun", "Bun", TOOL, name_is_ambiguous=True),
)


INTERESTS: tuple[InterestDef, ...] = (
    InterestDef(
        "ai-ml",
        "AI / machine learning",
        synonyms=(
            "ai", "artificial intelligence", "machine learning", "deep learning", "ml",
            "llm", "llms", "large language model", "large language models", "neural network",
            "neural networks", "nlp", "natural language processing", "computer vision",
            "generative ai", "genai", "reinforcement learning", "data science",
        ),
        topics=(
            "ai", "machine-learning", "deep-learning", "artificial-intelligence", "llm",
            "llms", "nlp", "computer-vision", "generative-ai", "neural-network",
            "reinforcement-learning", "data-science", "pytorch", "tensorflow", "langchain",
            "openai", "chatgpt", "huggingface", "transformers", "ml", "rag",
        ),
    ),
    InterestDef(
        "developer-tooling",
        "Developer tooling",
        synonyms=(
            "developer tools", "developer tool", "developer tooling", "devtools",
            "dev tools", "developer experience", "cli", "command-line tool",
            "command line tool", "linter", "code generator", "vscode extension",
            "static analysis",
        ),
        topics=(
            "developer-tools", "devtools", "cli", "command-line", "command-line-tool",
            "linter", "vscode-extension", "ide", "static-analysis", "tooling",
            "developer-experience", "code-generation", "productivity",
        ),
    ),
    InterestDef(
        "open-source",
        "Open source",
        synonyms=("open source", "open-source", "oss", "foss", "free software"),
        topics=("open-source", "opensource", "hacktoberfest", "oss", "foss"),
    ),
    InterestDef(
        "web-development",
        "Web development",
        synonyms=(
            "web development", "web app", "web apps", "web application", "web applications",
            "website", "frontend", "front-end", "backend", "back-end", "full stack",
            "full-stack", "fullstack", "rest api", "web developer",
        ),
        topics=(
            "web", "webapp", "web-development", "website", "frontend", "backend", "fullstack",
            "rest-api", "api", "web-application", "spa", "full-stack",
        ),
    ),
    InterestDef(
        "databases",
        "Databases",
        synonyms=("database", "databases", "query engine", "data modeling", "storage engine"),
        topics=("database", "databases", "sql", "orm", "nosql", "storage-engine", "key-value"),
    ),
    InterestDef(
        "infrastructure-cloud",
        "Infrastructure / cloud",
        synonyms=(
            "cloud", "infrastructure", "serverless", "cloud native", "cloud-native",
            "distributed systems", "infrastructure as code",
        ),
        topics=(
            "cloud", "infrastructure", "serverless", "cloud-native", "distributed-systems",
            "aws", "gcp", "azure", "iac", "infrastructure-as-code",
        ),
    ),
    InterestDef(
        "devops",
        "DevOps",
        synonyms=(
            "devops", "ci/cd", "continuous integration", "continuous delivery",
            "continuous deployment", "sre", "site reliability", "observability", "monitoring",
        ),
        topics=(
            "devops", "ci", "cicd", "ci-cd", "continuous-integration", "docker", "kubernetes",
            "monitoring", "observability", "sre", "github-actions",
        ),
    ),
    InterestDef(
        "security",
        "Security",
        synonyms=(
            "security", "cybersecurity", "infosec", "penetration testing", "pentesting",
            "vulnerability", "vulnerabilities", "cryptography", "ctf", "appsec", "malware",
        ),
        topics=(
            "security", "cybersecurity", "infosec", "pentesting", "penetration-testing",
            "cryptography", "ctf", "vulnerability", "appsec", "encryption", "malware-analysis",
        ),
    ),
    InterestDef(
        "data-engineering",
        "Data engineering",
        synonyms=(
            "data engineering", "data pipeline", "data pipelines", "etl", "elt",
            "data warehouse", "big data", "stream processing", "analytics",
        ),
        topics=(
            "data-engineering", "etl", "data-pipeline", "big-data", "apache-spark", "airflow",
            "kafka", "dbt", "data-warehouse", "analytics", "streaming", "data-analysis",
        ),
    ),
    InterestDef(
        "mobile-development",
        "Mobile development",
        synonyms=("mobile", "android", "ios", "mobile app", "mobile apps", "react native"),
        topics=(
            "android", "ios", "mobile", "flutter", "react-native", "mobile-app", "swiftui",
            "jetpack-compose",
        ),
    ),
    InterestDef(
        "systems-programming",
        "Systems programming",
        synonyms=(
            "systems programming", "operating system", "operating systems", "kernel",
            "compiler", "compilers", "interpreter", "low-level", "virtual machine",
        ),
        topics=(
            "operating-system", "os", "kernel", "compiler", "systems-programming",
            "interpreter", "virtual-machine", "low-level", "emulator",
        ),
    ),
    InterestDef(
        "game-development",
        "Game development",
        synonyms=("game", "games", "game development", "gamedev", "game engine"),
        topics=(
            "game", "games", "gamedev", "game-development", "game-engine", "unity", "unity3d",
            "godot", "unreal-engine", "pygame",
        ),
    ),
    InterestDef(
        "scientific-computing",
        "Scientific computing",
        synonyms=(
            "scientific computing", "simulation", "simulations", "numerical", "bioinformatics",
            "physics", "computational", "research software",
        ),
        topics=(
            "scientific-computing", "simulation", "bioinformatics", "physics",
            "numerical-methods", "research", "mathematics", "hpc", "computational-biology",
            "astronomy",
        ),
    ),
    InterestDef(
        "education",
        "Education",
        synonyms=(
            "education", "educational", "tutorial", "tutorials", "course", "teaching",
            "learning resources",
        ),
        topics=(
            "education", "tutorial", "tutorials", "learning", "course", "teaching",
            "educational", "100daysofcode", "learn",
        ),
    ),
    InterestDef(
        "blockchain",
        "Blockchain / Web3",
        synonyms=("blockchain", "web3", "smart contract", "smart contracts", "ethereum", "defi"),
        topics=(
            "blockchain", "web3", "ethereum", "smart-contracts", "solidity", "defi", "nft",
            "bitcoin", "cryptocurrency",
        ),
    ),
    InterestDef(
        "embedded-iot",
        "Embedded / IoT",
        synonyms=(
            "embedded", "iot", "internet of things", "microcontroller", "microcontrollers",
            "arduino", "raspberry pi", "firmware",
        ),
        topics=(
            "embedded", "iot", "arduino", "raspberry-pi", "esp32", "microcontroller",
            "firmware", "embedded-systems",
        ),
    ),
)
# fmt: on


# --- normalization ----------------------------------------------------------------------


def icon_token(value: str) -> str:
    """Normalize a badge/icon identifier or name: ``Node.js`` → ``nodedotjs``,
    ``C++`` → ``cplusplus``, ``c%2B%2B`` → ``cplusplus``, ``C#`` → ``csharp``."""
    value = unquote(value).lower().replace("+", "plus").replace("#", "sharp")
    value = value.replace(".", "dot")
    return re.sub(r"[^a-z0-9]", "", value)


def _topic_form(value: str) -> str:
    value = value.lower().replace("+", "plus").replace("#", "sharp").replace(".", "")
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def normalize_dependency(ecosystem: str, name: str) -> str:
    """Canonical dependency name per ecosystem (PyPI per PEP 503, the rest lowercased)."""
    name = name.strip().lower()
    if ecosystem == "pypi":
        return re.sub(r"[-_.]+", "-", name)
    return name


# --- lookup indexes (built once at import) ----------------------------------------------

SKILLS_BY_SLUG: dict[str, SkillDef] = {s.slug: s for s in SKILLS}
INTERESTS_BY_SLUG: dict[str, InterestDef] = {i.slug: i for i in INTERESTS}


def _index_phrases() -> tuple[dict[str, str], dict[str, str]]:
    plain: dict[str, str] = {}
    ambiguous: dict[str, str] = {}
    for skill in SKILLS:
        for alias in skill.aliases:
            plain.setdefault(alias, skill.slug)
        for alias in skill.ambiguous:
            ambiguous.setdefault(alias, skill.slug)
    return plain, ambiguous


PLAIN_PHRASES, AMBIGUOUS_PHRASES = _index_phrases()

LINGUIST_INDEX: dict[str, str] = {lang.lower(): s.slug for s in SKILLS for lang in s.linguist}


def _skill_topics(skill: SkillDef) -> list[str]:
    # Aliases like ".net" would become the generic topic "net"; they need explicit topics.
    names = [a for a in (*skill.aliases, *skill.ambiguous) if not a.startswith(".")]
    forms = [skill.slug, *skill.topics, *(_topic_form(a) for a in names)]
    return [f for f in dict.fromkeys(forms) if f]


TOPIC_INDEX: dict[str, str] = {}
for _skill in SKILLS:
    for _topic in _skill_topics(_skill):
        TOPIC_INDEX.setdefault(_topic, _skill.slug)

ICON_INDEX: dict[str, str] = {}
for _skill in SKILLS:
    for _value in (_skill.slug, _skill.name, *_skill.aliases, *_skill.ambiguous, *_skill.icons):
        ICON_INDEX.setdefault(icon_token(_value), _skill.slug)


def _dependency_indexes() -> tuple[dict[tuple[str, str], str], list[tuple[str, str, str]]]:
    exact: dict[tuple[str, str], str] = {}
    prefixes: list[tuple[str, str, str]] = []
    for skill in SKILLS:
        for eco, names in skill.deps.items():
            ecosystems = JVM_ECOSYSTEMS if eco == "jvm" else (eco,)
            for target in ecosystems:
                for dep in names:
                    if dep.endswith("*"):
                        prefixes.append(
                            (target, normalize_dependency(target, dep[:-1]), skill.slug)
                        )
                    else:
                        exact.setdefault((target, normalize_dependency(target, dep)), skill.slug)
    # Longest prefix first, so the most specific rule wins.
    prefixes.sort(key=lambda p: len(p[1]), reverse=True)
    return exact, prefixes


DEPENDENCY_INDEX, DEPENDENCY_PREFIXES = _dependency_indexes()

INTEREST_TOPIC_INDEX: dict[str, str] = {}
for _interest in INTERESTS:
    for _topic in _interest.topics:
        INTEREST_TOPIC_INDEX.setdefault(_topic, _interest.slug)


# --- lookups ------------------------------------------------------------------------------


def skill_for_linguist(language: str) -> str | None:
    return LINGUIST_INDEX.get(language.lower())


def skill_for_topic(topic: str) -> str | None:
    return TOPIC_INDEX.get(topic.lower())


def skill_for_icon(token: str) -> str | None:
    return ICON_INDEX.get(icon_token(token))


def skill_for_dependency(ecosystem: str, name: str) -> str | None:
    normalized = normalize_dependency(ecosystem, name)
    if slug := DEPENDENCY_INDEX.get((ecosystem, normalized)):
        return slug
    for eco, prefix, slug in DEPENDENCY_PREFIXES:
        if eco == ecosystem and normalized.startswith(prefix):
            return slug
    return None


def interest_for_topic(topic: str) -> str | None:
    return INTEREST_TOPIC_INDEX.get(topic.lower())
