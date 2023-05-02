#!/usr/bin/env bash
CRONTASK=/etc/cron.d/crontask

cat > ${CRONTASK} <<EOF
SHELL=/bin/bash
PATH=/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
CRON_TZ=Asia/Shanghai

# *  *  *  *  * user-name command to be executed
${SCHEDULE} root . /opt/venv/bin/activate && cd /data && xdufacool ${TASKFILE} > /proc/1/fd/1
EOF

# cat ${CRONTASK}
# chmod 0644 ${CRONTASK}
# crontab ${CRONTASK}
# crontab -l

/usr/sbin/cron -f
