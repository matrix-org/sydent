FROM docker.io/python:3-alpine

RUN apk add --no-cache --virtual .nacl_deps \
        build-base \
        libressl-dev \
        libffi-dev

COPY . /sydent
WORKDIR /sydent
RUN cd /sydent \
    && pip install --upgrade pip setuptools sentry-sdk \
    && pip install -e .

ENV SYDENT_CONF=/data/sydent.conf
ENV SYDENT_PID_FILE=/data/sydent.pid
ENV SYDENT_DB_PATH=/data/sydent.db

VOLUME ["/data"]
EXPOSE 8090/tcp
ENTRYPOINT [ "python", "-m", "sydent.sydent" ]
