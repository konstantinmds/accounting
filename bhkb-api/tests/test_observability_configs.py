import json
from pathlib import Path

import yaml


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_yaml(path: Path):
    with path.open() as handle:
        return yaml.safe_load(handle)


def test_compose_services_and_ports():
    compose = load_yaml(repo_root() / "compose.obs.yml")
    services = compose.get("services", {})
    expected = {"prometheus", "grafana", "loki", "tempo"}
    assert expected.issubset(services.keys())

    prometheus_ports = services["prometheus"].get("ports", [])
    grafana_ports = services["grafana"].get("ports", [])
    loki_ports = services["loki"].get("ports", [])
    tempo_ports = services["tempo"].get("ports", [])

    assert "9090:9090" in prometheus_ports
    assert "3001:3000" in grafana_ports
    assert "3100:3100" in loki_ports
    assert "3200:3200" in tempo_ports

    assert "host.docker.internal:host-gateway" in services["prometheus"].get(
        "extra_hosts", []
    )


def test_prometheus_scrape_jobs():
    prom_cfg = load_yaml(repo_root() / "ops" / "prometheus.yml")
    jobs = {job["job_name"]: job for job in prom_cfg.get("scrape_configs", [])}

    for job_name, target in [
        ("prometheus", "localhost:9090"),
        ("api", "host.docker.internal:8000"),
        ("worker", "host.docker.internal:8001"),
        ("watcher", "host.docker.internal:8002"),
    ]:
        assert job_name in jobs
        static_configs = jobs[job_name].get("static_configs", [])
        targets = static_configs[0].get("targets", []) if static_configs else []
        assert target in targets


def test_grafana_datasources():
    datasources = load_yaml(
        repo_root() / "ops" / "grafana" / "provisioning" / "datasources" / "datasource.yaml"
    ).get("datasources", [])
    by_uid = {ds["uid"]: ds for ds in datasources}

    assert by_uid["prometheus-ds"]["url"] == "http://prometheus:9090"
    assert by_uid["prometheus-ds"]["type"] == "prometheus"
    assert by_uid["prometheus-ds"].get("isDefault") is True

    assert by_uid["loki-ds"]["url"] == "http://loki:3100"
    assert by_uid["loki-ds"]["type"] == "loki"

    tempo_ds = by_uid["tempo-ds"]
    assert tempo_ds["url"] == "http://tempo:3200"
    assert tempo_ds["type"] == "tempo"
    traces_to_logs = tempo_ds.get("jsonData", {}).get("tracesToLogs", {})
    assert traces_to_logs.get("datasourceUid") == "loki-ds"


def test_dashboard_panels_and_queries():
    dashboard_path = (
        repo_root()
        / "ops"
        / "grafana"
        / "provisioning"
        / "dashboards"
        / "spec1_overview.json"
    )
    dashboard = json.loads(dashboard_path.read_text())
    panels = dashboard.get("panels", [])
    titles = {panel.get("title") for panel in panels}

    assert {
        "Watcher Files Seen Rate",
        "Ingest Tasks by Status (5m increase)",
        "API Latency (p95 placeholder)",
        "API Logs (Loki)",
        "Recent Traces (Tempo)",
    }.issubset(titles)

    expressions = [
        target.get("expr")
        for panel in panels
        for target in panel.get("targets", [])
        if "expr" in target
    ]
    queries = [
        target.get("query")
        for panel in panels
        for target in panel.get("targets", [])
        if "query" in target
    ]

    assert "rate(watcher_files_seen_total[5m])" in expressions
    assert "sum by (status)(increase(ingest_tasks_total[5m]))" in expressions
    assert "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, handler))" in expressions
    assert "{} | limit 20" in queries
