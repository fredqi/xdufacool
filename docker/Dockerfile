ARG PIXI_VERSION=0.64.0
FROM ghcr.io/prefix-dev/pixi:${PIXI_VERSION} AS pixi

FROM ubuntu:noble

ARG DEBIAN_FRONTEND=noninteractive
ARG APP_USER=xdufacool

RUN apt-get update -qq && \
    apt-get upgrade -qq && \
    apt-get install -qq --no-install-recommends -y tzdata cron ca-certificates && \
    ln -fs /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean && \
    rm -r /var/lib/apt/lists/*

COPY --from=pixi /usr/local/bin/pixi /usr/local/bin/pixi
RUN pixi --version

COPY . /app
RUN groupadd --system ${APP_USER} && \
    useradd --system --gid ${APP_USER} --create-home --shell /bin/bash ${APP_USER}
RUN mkdir -p /data && chown -R ${APP_USER}:${APP_USER} /app /data

WORKDIR /app
RUN pixi install --locked --environment default
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /data
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
