TARGET = mlad

all: $(TARGET)

.PHONY: clean

clean:
	@docker stop mlad-build-env | xargs docker rm >> /dev/null 2>&1
	@rm -rf dist

$(TARGET): helm-charts cli

helm-charts:
	@cd charts && bash update.sh

build-cli:
	@docker build -t mlappdeploy-build-env:latest -f assets/Dockerfile_CLI . || :

cli: build-cli
	@mkdir -p bin
	@docker run -it --name mlad-build-env mlappdeploy-build-env:latest
	@docker cp mlad-build-env:/build/dist/mlad-static bin/$(TARGET)
	@docker stop mlad-build-env | xargs docker rm

install:
	@cp bin/$(TARGET) ${HOME}/.local/bin/
	@echo Install completed.

debug: build-cli
	@mkdir -p dist.tmp
	@docker run -it --rm -v ${PWD}/dist.tmp:/build/dist mlappdeploy-build-env:latest /bin/bash

api-server:
	@$(eval CONTEXT := $(shell mlad config ls | grep "*" | awk '{print $$2}'))
	@$(eval REGISTRY := $(shell mlad config get $(CONTEXT) docker.registry.address | head -n1 | grep -oP 'http[s]?://\K\S+'))
	@echo ${REGISTRY}
	@docker build -t ${REGISTRY}/mlappdeploy/api-server:latest -f assets/Dockerfile .
	@docker push ${REGISTRY}/mlappdeploy/api-server:latest
	@helm upgrade mlad charts/api-server --create-namespace -n mlad --set image.repository=${REGISTRY}/mlappdeploy/api-server --set image.tag=latest