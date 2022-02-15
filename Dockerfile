FROM python:3.7-slim

COPY python /workspace

WORKDIR /workspace

RUN python setup.py install

EXPOSE 8440

ENTRYPOINT python -m mlad.service
