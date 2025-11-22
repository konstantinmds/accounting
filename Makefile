COMPOSE ?= docker compose
ENV_FILE ?= .env

.PHONY: up down ps logs-% healthcheck restart

up:
	$(COMPOSE) --env-file $(ENV_FILE) up -d

down:
	$(COMPOSE) --env-file $(ENV_FILE) down

ps:
	$(COMPOSE) --env-file $(ENV_FILE) ps

logs-%:
	$(COMPOSE) --env-file $(ENV_FILE) logs -f $*

healthcheck:
	@echo "Checking services..."
	@curl -fsS http://localhost:9200/_cluster/health >/dev/null && echo "elasticsearch: OK"
	@curl -fsS http://localhost:9000/minio/health/live >/dev/null && echo "minio: OK"
	@POSTGRES_USER=$${POSTGRES_USER:-postgres}; POSTGRES_DB=$${POSTGRES_DB:-spec1}; $(COMPOSE) --env-file $(ENV_FILE) exec -T postgres pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB -h 127.0.0.1 >/dev/null && echo "postgres: OK"
	@curl -fsS http://localhost:8088/ >/dev/null && echo "temporal-ui: OK"
	@echo "Done."

restart:
	$(COMPOSE) --env-file $(ENV_FILE) down && $(COMPOSE) --env-file $(ENV_FILE) up -d
