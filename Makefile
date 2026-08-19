# ai-draw: the app, in containers.
#
#   make up      build and start; prints the URL
#   make down    stop, keeping the job database
#   make clean   stop and delete the job database volume
#
# Ports are overridable: `make up UI_PORT=3000 API_PORT=9000`.

COMPOSE  ?= docker compose
UI_PORT  ?= 8080
API_PORT ?= 8000
export UI_PORT
export API_PORT

.DEFAULT_GOAL := help
.PHONY: help up down restart clean build rebuild logs ps test shell cards

help: ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-9s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  UI  http://localhost:$(UI_PORT)"
	@echo "  API http://localhost:$(API_PORT)/api/health"

up: ## Build if needed and start the app
	$(COMPOSE) up -d --build
	@echo ""
	@echo "  ai-draw is up:  http://localhost:$(UI_PORT)"
	@echo "  API health:     http://localhost:$(API_PORT)/api/health"

down: ## Stop the app, keeping queued and finished jobs
	$(COMPOSE) down --remove-orphans

restart: ## Restart both containers without rebuilding
	$(COMPOSE) restart

clean: ## Stop the app and delete the job database volume
	@echo "This deletes every queued and finished job in the container volume."
	$(COMPOSE) down --volumes --remove-orphans

build: ## Build the images
	$(COMPOSE) build

rebuild: ## Build the images from scratch, ignoring the layer cache
	$(COMPOSE) build --no-cache

logs: ## Follow both containers' logs
	$(COMPOSE) logs -f

ps: ## Show container and health status
	$(COMPOSE) ps

test: ## Run the API test suite inside the image
	$(COMPOSE) run --rm --no-deps api python -m pytest -q

shell: ## Open a shell in the API container
	$(COMPOSE) run --rm --no-deps api bash

cards: ## Re-derive data/pilot-864/cards.json and fail if the committed copy is stale
	python3 tools/gen_card_index.py --check
