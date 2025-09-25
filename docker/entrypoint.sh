#!/usr/bin/env bash
CRONTASK=/etc/cron.d/crontask
CLI=/usr/local/bin/xdufacool_check

cat > ${CRONTASK} <<EOF
SHELL=/bin/bash
PATH=/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
CRON_TZ=Asia/Shanghai

# *  *  *  *  * user-name command to be executed
${SCHEDULE} root ${CLI} > /proc/1/fd/1
EOF

cat > ${CLI} <<EOF
#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin"
source /opt/venv/bin/activate

if [ -f "${WORKDIR}/${TASKFILE}" ]; then
    cd ${WORKDIR}
    exec xdufacool check -b ${WORKDIR} -c ${TASKFILE}
else
    echo "${TASKFILE} not found in ${WORKDIR}"
fi
EOF

/usr/bin/chmod +x ${CLI}
/usr/sbin/cron -f