COMPOSE ?= docker compose
ENV_FILE ?= .env

.PHONY: up down ps logs-% healthcheck restart \
        up-obs down-obs up-all down-all ps-all restart-all healthcheck-obs healthcheck-all

# Core services (Postgres, MinIO, Elasticsearch, Temporal)
up:
	$(COMPOSE) --env-file $(ENV_FILE) up -d

down:
	$(COMPOSE) --env-file $(ENV_FILE) down

ps:
	$(COMPOSE) --env-file $(ENV_FILE) ps

logs-%:
	$(COMPOSE) --env-file $(ENV_FILE) logs -f $*

healthcheck:
	@echo "Checking core services..."
	@curl -fsS http://localhost:9200/_cluster/health >/dev/null && echo "elasticsearch: OK"
	@curl -fsS http://localhost:9000/minio/health/live >/dev/null && echo "minio: OK"
	@POSTGRES_USER=$${POSTGRES_USER:-postgres}; POSTGRES_DB=$${POSTGRES_DB:-spec1}; $(COMPOSE) --env-file $(ENV_FILE) exec -T postgres pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB -h 127.0.0.1 >/dev/null && echo "postgres: OK"
	@curl -fsS http://localhost:8088/ >/dev/null && echo "temporal-ui: OK"
	@echo "Done."

restart:
	$(COMPOSE) --env-file $(ENV_FILE) down && $(COMPOSE) --env-file $(ENV_FILE) up -d

# Observability services (Prometheus, Grafana, Tempo, Loki)
up-obs:
	$(COMPOSE) -f compose.obs.yml up -d

down-obs:
	$(COMPOSE) -f compose.obs.yml down

healthcheck-obs:
	@echo "Checking observability services..."
	@curl -fsS http://localhost:9090/-/ready >/dev/null && echo "prometheus: OK"
	@curl -fsS http://localhost:3001/api/health >/dev/null && echo "grafana: OK"
	@curl -fsS http://localhost:3100/ready >/dev/null && echo "loki: OK"
	@curl -fsS http://localhost:3200/ready >/dev/null && echo "tempo: OK"
	@echo "Done."

# Combined operations (core + observability)
up-all:
	@echo "Starting core services..."
	@$(COMPOSE) --env-file $(ENV_FILE) up -d
	@echo "Starting observability services..."
	@$(COMPOSE) -f compose.obs.yml up -d
	@echo "All services started."

down-all:
	@echo "Stopping all services..."
	@$(COMPOSE) -f compose.obs.yml down
	@$(COMPOSE) --env-file $(ENV_FILE) down
	@echo "All services stopped."

ps-all:
	@echo "Core services:"
	@$(COMPOSE) --env-file $(ENV_FILE) ps
	@echo ""
	@echo "Observability services:"
	@$(COMPOSE) -f compose.obs.yml ps

restart-all:
	@$(MAKE) down-all
	@$(MAKE) up-all

healthcheck-all:
	@$(MAKE) healthcheck
	@echo ""
	@$(MAKE) healthcheck-obs
