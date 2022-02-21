FROM        python:3.9-slim
COPY        python /workspace
WORKDIR     /workspace
RUN         python setup.py install
EXPOSE      8440
ENTRYPOINT  python -m mlad.service
