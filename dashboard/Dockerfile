FROM node:14-slim

WORKDIR /app
COPY dashboard/frontend /app
RUN yarn && yarn build


FROM python:3.7-slim

WORKDIR /app

RUN mkdir ./static
COPY --from=0 /app/build ./static

COPY dashboard/backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY dashboard/backend /app

LABEL MLAD_BOARD=""

ENTRYPOINT ["gunicorn", \
            "-k", "uvicorn.workers.UvicornWorker", \
            "-b", "0.0.0.0:2021", \
            "--error-logfile", "-", \
            "--access-logfile", "-", \
            "entry:app"]