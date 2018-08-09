FROM docker.io/python:2-alpine3.7

RUN apk add --no-cache --virtual .nacl_deps \
        build-base \
        libressl-dev \
        libffi-dev

COPY . /sydent
WORKDIR /sydent
RUN cd /sydent \
    && pip install --upgrade pip setuptools \
    && pip install --upgrade .

ENV SYDENT_CONF=/data/sydent.conf
ENV SYDENT_DB_PATH=/data/sydent.db
VOLUME ["/data"]
EXPOSE 8090/tcp
ENTRYPOINT [ "python", "-m", "sydent.sydent" ]
