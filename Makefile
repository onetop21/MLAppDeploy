TARGET = mlad

all: $(TARGET)

.PHONY: clean

clean:
	docker stop mlad-build-env | xargs docker rm

$(TARGET): env build

env:
	docker build -t mlappdeploy-build-env:latest -f assets/Dockerfile_CLI . || :

build: clean
	mkdir -p dist
	docker run -it --name mlad-build-env -v ${PWD}/python:/build/python mlappdeploy-build-env:latest
	docker cp mlad-build-env:/build/dist/mlad-static dist/$(TARGET)
	docker stop mlad-build-env | xargs docker rm

install:
	cp dist/$(TARGET) ${HOME}/.local/bin/

debug:
	docker run -it --rm -v ${PWD}/python:/build/python -v ${PWD}/debug:/build/dist mlappdeploy-build-env:latest /bin/bash

	