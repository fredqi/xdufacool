#!/usr/bin/env bash
set -euo pipefail

CRONTASK=/etc/cron.d/crontask
CLI=/usr/local/bin/xdufacool_check
PIXI=/usr/local/bin/pixi

WORKDIR=${WORKDIR:-/data}
TASKFILE=${TASKFILE:-PRML.yml}
APP_USER=${APP_USER:-xdufacool}
MANIFEST_PATH=${MANIFEST_PATH:-/app/pixi.toml}

cat > ${CRONTASK} <<EOF
SHELL=/bin/bash
PATH=/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
CRON_TZ=Asia/Shanghai
HOME=/home/${APP_USER}

# *  *  *  *  * user-name command to be executed
${SCHEDULE} ${APP_USER} ${CLI} > /proc/1/fd/1 2>&1
EOF

cat > ${CLI} <<EOF
#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin"

if [ -f "${WORKDIR}/${TASKFILE}" ]; then
    cd "${WORKDIR}"
    exec ${PIXI} run --manifest-path "${MANIFEST_PATH}" -e default xdufacool check -b "${WORKDIR}" -c "${TASKFILE}"
else
    echo "${TASKFILE} not found in ${WORKDIR}" >&2
fi
EOF

/usr/bin/chmod +x ${CLI}
/usr/sbin/cron -f