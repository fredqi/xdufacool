FROM ubuntu:focal

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update -qq && \
    apt-get upgrade -qq && \
    apt-get install -qq --no-install-recommends -y cron python3-venv && \
    apt-get clean && \
    rm -r /var/lib/apt/lists/*

COPY crontab /etc/cron.d/xdufacool
RUN chmod 0644 /etc/cron.d/xdufacool &&\
    crontab /etc/cron.d/xdufacool

RUN python3 -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install --no-cache-dir https://github.com/fredqi/xdufacool/archive/master.zip

WORKDIR /data
