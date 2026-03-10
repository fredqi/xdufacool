#!/usr/bin/env bash
set -euo pipefail

CRONTASK=/etc/cron.d/crontask
CLI=/usr/local/bin/xdufacool_check
XDUFACOOL_BIN=/opt/venv/bin/xdufacool

WORKDIR=${WORKDIR:-/data}
TASKFILE=${TASKFILE:-PRML.yml}
APP_USER=${APP_USER:-ubuntu}

cat > ${CRONTASK} <<EOF
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/sbin:/usr/bin
CRON_TZ=Asia/Shanghai
HOME=/home/${APP_USER}

# *  *  *  *  * user-name command to be executed
${SCHEDULE} root su -s /bin/bash -c '${CLI}' ${APP_USER} > /proc/1/fd/1 2>&1
EOF

cat > ${CLI} <<EOF
#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/bin:/usr/sbin:/usr/bin"

if [ -f "${WORKDIR}/${TASKFILE}" ]; then
    cd "${WORKDIR}"
    exec ${XDUFACOOL_BIN} check -b "${WORKDIR}" -c "${TASKFILE}"
else
    echo "${TASKFILE} not found in ${WORKDIR}" >&2
fi
EOF

/usr/bin/chmod +x ${CLI}
/usr/sbin/cron -f