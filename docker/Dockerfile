FROM ubuntu:noble

ARG DEBIAN_FRONTEND=noninteractive
ARG APP_USER=xdufacool

RUN apt-get update -qq && \
    apt-get upgrade -qq && \
    apt-get install -qq --no-install-recommends -y \
      ca-certificates \
      cron \
      python3 \
      python3-pip \
      python3-venv \
      tzdata && \
    ln -fs /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean && \
    rm -r /var/lib/apt/lists/*

COPY . /app
RUN groupadd --system ${APP_USER} && \
    useradd --system --gid ${APP_USER} --create-home --shell /bin/bash ${APP_USER}
RUN mkdir -p /data && chown -R ${APP_USER}:${APP_USER} /app /data

WORKDIR /app
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install .

ENV PATH="/opt/venv/bin:${PATH}"

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /data
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
