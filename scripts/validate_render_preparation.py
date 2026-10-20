"""Offline structural checks only: no app imports, env reads, network or cloud I/O.

This does not replace Render schema validation, builds, startup or runtime testing.
The production .template must remain intentionally non-deployable.
"""
import ast
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


class UniqueKeysLoader(yaml.SafeLoader):
    pass


def mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeysLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)


def load(name):
    return yaml.load((ROOT / name).read_text(encoding="utf-8"), Loader=UniqueKeysLoader)


def variables(service):
    env = service.get("envVars", [])
    keys = [item["key"] for item in env]
    assert len(keys) == len(set(keys)), "Duplicate service environment variable"
    for item in env:
        if any(secret in item["key"] for secret in ("PASSWORD", "SERVICE_KEY", "API_KEY", "REDIS_URL")):
            assert "value" not in item, "Inline secret value in Blueprint"
    return {item["key"]: item.get("value") for item in env}


def service_paths(service):
    if service.get("runtime") == "docker":
        root = (ROOT / service["rootDir"]).resolve()
        context = (root / service["dockerContext"]).resolve()
        dockerfile = (root / service["dockerfilePath"]).resolve()
        assert context.is_relative_to(ROOT) and dockerfile.is_relative_to(ROOT)
        assert context.is_dir() and dockerfile.is_file()
    if service.get("runtime") == "static":
        assert service["rootDir"] == "frontend"
        assert service["buildCommand"] == "npm ci && npm run build"
        assert service["staticPublishPath"] == "./dist"
        assert {"type": "rewrite", "source": "/*", "destination": "/index.html"} in service["routes"]
        assert set(variables(service)) == {"VITE_API_URL", "VITE_DEPLOYMENT_MODE"}


def main():
    sources = list((ROOT / "backend/app").rglob("*.py"))
    for source in sources:
        ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source))
    print(f"Python AST parsing passed: {len(sources)} application files (not imported/executed).")
    staging = load("render.yaml")["services"]
    production = load("render.production.yaml.template")["services"]
    load("backend/docker-compose.yml")
    assert len(staging) == 2 and all(service["type"] == "web" for service in staging)
    assert len({service["name"] for service in staging + production}) == len(staging + production)
    for service in staging + production:
        service_paths(service)
        variables(service)
        if service["type"] != "keyvalue":
            assert service["autoDeployTrigger"] == "off"
    api = next(service for service in staging if service["runtime"] == "docker")
    assert variables(api)["DEPLOYMENT_MODE"] == "staging"
    assert variables(api)["DEMO_MODE"] == "true"
    assert api["healthCheckPath"] == "/ready" and api["plan"] == "free"
    queue = next(service for service in production if service["type"] == "keyvalue")
    assert queue["ipAllowList"] == [] and queue["maxmemoryPolicy"] == "noeviction"
    assert queue["persistenceMode"] == "journal-snapshot" and queue["plan"] != "free"
    worker = next(service for service in production if service["type"] == "worker")
    assert worker["dockerCommand"] == "python -m app.production_preflight"
    assert worker["region"] == "APPROVED_REGION_REQUIRED"
    assert worker["branch"] == "APPROVED_RELEASE_BRANCH_REQUIRED"
    for service in production:
        if service.get("runtime") == "docker":
            assert variables(service)["DEPLOYMENT_MODE"] == "production"
    print("YAML parsing/duplicate-key, paths, public-env and staging structural checks passed.")
    print("Production template has deliberate region/branch placeholders and a nonfunctional worker stub.")
    print("NOT checked: Render API/schema, images, dependencies, startup, requests, auth, jobs or Supabase.")


if __name__ == "__main__":
    main()
