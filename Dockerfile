#
# Step 1: Build sydent and install dependencies
#
FROM docker.io/python:3-alpine as builder

# Install dev packages
RUN apk add --no-cache \
        build-base \
        libressl-dev \
        libffi-dev

# Copy resources
COPY ["res", "/sydent/res"]
COPY ["scripts", "/sydent/scripts"]
COPY ["sydent", "/sydent/sydent"]
COPY ["README.rst", "setup.cfg", "setup.py", "/sydent/"]

# Install dependencies
RUN cd /sydent \
    && pip install --user --upgrade pip setuptools sentry-sdk \
    && pip install --user -e . \
    && rm -rf /root/.cache \
    && find /sydent -name '*.pyc' -delete

#
# Step 2: Reduce image size and layers
#

FROM docker.io/python:3-alpine

# Install packages
RUN apk add --no-cache \
        libressl \
        libffi

# Copy dependencies and sydent
COPY --from=builder ["/root/.local", "/root/.local"]
COPY --from=builder ["/sydent", "/sydent"]

ENV SYDENT_CONF=/data/sydent.conf
ENV SYDENT_PID_FILE=/data/sydent.pid
ENV SYDENT_DB_PATH=/data/sydent.db

WORKDIR /sydent
VOLUME ["/data"]
EXPOSE 8090/tcp
CMD [ "python", "-m", "sydent.sydent" ]
