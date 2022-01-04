FROM python:3.8-slim

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update -qq && \
    apt-get upgrade -qq && \
    apt-get install -qq --no-install-recommends -y cron &&\
    apt-get clean && \
    rm -r /var/lib/apt/lists/*

RUN python3 -m pip install --upgrade pip && \
    pip install https://github.com/fredqi/xdufacool/archive/master.zip

COPY crontab /etc/cron.d/xdufacool
RUN chmod 0644 /etc/cron.d/xdufacool &&\
    crontab /etc/cron.d/xdufacool

WORKDIR /data
ENTRYPOINT ["cron", "-f", "-l", "2"]
