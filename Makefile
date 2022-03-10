TARGET = mlad

all: $(TARGET)

.PHONY: clean

clean:
	@docker stop mlad-build-env | xargs docker rm >> /dev/null 2>&1
	@rm -rf dist

$(TARGET): helm-charts cli

helm-charts:
	@cd charts && bash update.sh

build:
	@docker build -t mlappdeploy-build-env:latest -f assets/Dockerfile_CLI . || :

cli: build
	@mkdir -p bin
	@docker run -it --name mlad-build-env -v ${PWD}/python:/build/python:ro mlappdeploy-build-env:latest
	@docker cp mlad-build-env:/build/dist/mlad-static bin/$(TARGET)
	@docker stop mlad-build-env | xargs docker rm

install:
	@cp bin/$(TARGET) ${HOME}/.local/bin/
	@echo Install completed.

debug: build
	@mkdir -p dist.tmp
	@docker run -it --rm -v ${PWD}/python:/build/python -v ${PWD}/dist.tmp:/build/dist mlappdeploy-build-env:latest /bin/bash
