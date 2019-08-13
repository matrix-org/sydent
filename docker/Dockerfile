FROM debian:buster-slim

RUN set -ex \
    && apt-get update \
    && apt-get install -y \
	build-essential \
	python2.7-dev \
	libffi-dev \
	sqlite3 \
	python-pip \
	libssl-dev \
	python-virtualenv \
	libxslt1-dev

# Install dependencies
RUN pip install https://github.com/matrix-org/sydent/tarball/master \
    && pip install --upgrade pip \
    && pip install --upgrade setuptools

# Copy in and run the start script
COPY ./sydent-ci.sh /sydent-ci.sh
