FROM ubuntu:focal

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update -qq && \
    apt-get upgrade -qq && \
    apt-get install -qq --no-install-recommends -y tzdata cron python3-venv && \
    ln -fs /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean && \
    rm -r /var/lib/apt/lists/*

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# RUN chmod 0644 /etc/cron.d/xdufacool &&\
#     crontab /etc/cron.d/xdufacool

RUN python3 -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install --no-cache-dir https://github.com/fredqi/xdufacool/archive/master.zip

WORKDIR /data
