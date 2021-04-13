#
# Step 1: Build sydent and install dependencies
#
FROM docker.io/python:3.8-slim as builder

# Install dev packages
RUN apt-get update && apt-get install -y \
    build-essential

# Add user sydent
RUN addgroup --system --gid 993 sydent \
    && adduser --disabled-password --home /sydent --system --uid 993 --gecos sydent sydent \
    && echo "sydent:$(dd if=/dev/random bs=32 count=1 | base64)" | chpasswd

# Copy resources
COPY --chown=sydent:sydent ["res", "/sydent/res"]
COPY --chown=sydent:sydent ["scripts", "/sydent/scripts"]
COPY --chown=sydent:sydent ["sydent", "/sydent/sydent"]
COPY --chown=sydent:sydent ["README.rst", "setup.cfg", "setup.py", "/sydent/"]

# Install dependencies
USER sydent
WORKDIR /sydent
RUN pip install --user --upgrade pip setuptools sentry-sdk prometheus_client \
    && pip install --user . \
    && rm -rf /sydent/.cache \
    && find /sydent -name '*.pyc' -delete

#
# Step 2: Reduce image size and layers
#

FROM docker.io/python:3.8-slim

# Add user sydent and create /data directory
RUN addgroup --system --gid 993 sydent \
    && adduser --disabled-password --home /sydent --system --uid 993 --gecos sydent sydent \
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
