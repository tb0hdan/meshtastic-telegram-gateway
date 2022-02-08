#!/bin/bash

cd $(dirname $0)

screen -t MESH -S MESH -d -m make run

