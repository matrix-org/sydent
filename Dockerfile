#
# Step 1: Build sydent and install dependencies
#
FROM docker.io/python:3-alpine as builder

# Install dev packages
RUN apk add --no-cache \
        build-base \
        libressl-dev \
        libffi-dev

# Add user sydent
RUN addgroup -S -g 993 sydent \
    && adduser -D --home /sydent -S -u 993 -G sydent -s /bin/ash sydent \
    && echo "sydent:$(dd if=/dev/random bs=32 count=1 | base64)" | chpasswd

# Copy resources
COPY --chown=sydent:sydent ["res", "/sydent/res"]
COPY --chown=sydent:sydent ["scripts", "/sydent/scripts"]
COPY --chown=sydent:sydent ["sydent", "/sydent/sydent"]
COPY --chown=sydent:sydent ["README.rst", "setup.cfg", "setup.py", "/sydent/"]

# Install dependencies
RUN cd /sydent \
    && su sydent -c 'pip install --user --upgrade pip setuptools sentry-sdk' \
    && su sydent -c 'pip install --user -e .' \
    && rm -rf /sydent/.cache \
    && find /sydent -name '*.pyc' -delete

#
# Step 2: Reduce image size and layers
#

FROM docker.io/python:3-alpine

# Install packages
RUN apk add --no-cache \
        libressl \
        libffi

# Add user sydent and create /data directory
RUN addgroup -S -g 993 sydent \
    && adduser -D --home /sydent -S -u 993 -G sydent -s /bin/ash sydent \
    && echo "sydent:$(dd if=/dev/random bs=32 count=1 | base64)" | chpasswd \
    && mkdir /data \
    && chown sydent:sydent /data

# Copy sydent
COPY --from=builder ["/sydent", "/sydent"]

ENV SYDENT_CONF=/data/sydent.conf
ENV SYDENT_PID_FILE=/data/sydent.pid
ENV SYDENT_DB_PATH=/data/sydent.db

WORKDIR /sydent
USER sydent:sydent
VOLUME ["/data"]
EXPOSE 8090/tcp
CMD [ "python", "-m", "sydent.sydent" ]
