#!/bin/bash

# slow startup
sleep 10

DEVICE=$(cat mesh.ini|egrep -v '^#'|egrep 'Device ='|awk -F' = ' '{print $2}')

# run monitoring
while :; do
    wget --timeout 3 -t 1 http://localhost:5000 -O /tmp/mtg.html >/dev/null 2>/dev/null
    if [ $? -ne 0 ]; then
        echo 'ERR!'
        mesh_pid=$(ps ax|grep 'python3 ./mesh.py'|grep -v 'grep'|awk '{print $1}')
        if [ "${mesh_pid}" != "" ]; then
            kill ${mesh_pid}
        fi
        acm_pid=$(lsof -n|grep ${DEVICE}|awk '{print $2}')
        if [ "${acm_pid}" != "" ]; then
            kill -9 ${acm_pid}
        fi
    fi
    sleep 60
done
