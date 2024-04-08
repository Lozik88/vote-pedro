#!/bin/bash
# FLASK_APP=flask --app webgui/main run &
# kill any existing flask instance
kill $(ps -a|grep flask|awk '{print $1}')

FLASK_APP=webgui/main.py flask run &
FLASK_PID=$!
python3 main.py
kill $FLASK_PID
