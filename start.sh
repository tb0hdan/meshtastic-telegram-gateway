#!/bin/bash

cd $(dirname $0)

screen -t MESH -S MESH -d -m sh -c 'make run >>logfile.out 2>>logfile.err'
screen -t MESH-MON -S MESH-MON -d -m sh -c './monitor.sh'

