TARGET = mlad

all: $(TARGET)

.PHONY: clean

clean:
	@docker stop mlad-build-env | xargs docker rm >> /dev/null 2>&1
	@rm -rf dist

$(TARGET): chart cli

chart:
	@cd charts && bash update.sh

cli:
	@mkdir -p bin
	@docker build -t mlappdeploy-build-env:latest -f assets/Dockerfile_CLI . || :
	@docker run -it --name mlad-build-env -v ${PWD}/python:/build/python:ro mlappdeploy-build-env:latest
	@docker cp mlad-build-env:/build/dist/mlad-static bin/$(TARGET)
	@docker stop mlad-build-env | xargs docker rm

install:
	@cp bin/$(TARGET) ${HOME}/.local/bin/

debug:
	@docker run -it --rm -v ${PWD}/python:/build/python -v ${PWD}/debug:/build/dist mlappdeploy-build-env:latest /bin/bash
