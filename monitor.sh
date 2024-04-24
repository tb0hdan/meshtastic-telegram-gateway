#!/bin/bash

# slow startup
sleep 10

DEVICE=$(cat mesh.ini|egrep -v '^#'|egrep 'Device ='|awk -F' = ' '{print $2}')

# run monitoring
while :; do
    wget --timeout 3 -t 1 http://localhost:5000 -O /tmp/mtg.html >/dev/null 2>/dev/null
    if [ $? -ne 0 ]; then
        echo 'ERR!'
        # kill stuck process
        mesh_pid=$(ps ax|grep 'python3 ./mesh.py'|grep -v 'grep'|awk '{print $1}')
        if [ "${mesh_pid}" != "" ]; then
            kill ${mesh_pid}
        fi
        # clear stuck device (skip for MQTT)
        acm_pid=$(lsof -n|grep ${DEVICE}|awk '{print $2}')
        if [ "${acm_pid}" != "" ] && [ "${DEVICE}" != "mqtt" ]; then
            kill -9 ${acm_pid}
        fi
        # Clear stuck pipes
        kill $(lsof -n -P 2>/dev/null|grep meshtastic|grep WebApp|grep pipe|awk '{print $2}'|sort -b -i -f -u)
    fi
    sleep 60
done
