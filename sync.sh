#!/bin/bash
rsync -avz --progress --exclude=.env src/ andras@192.168.0.81:~/frame/
