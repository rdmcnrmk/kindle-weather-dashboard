#!/bin/sh
# Weather Dashboard — Eindhoven, Open-Meteo, hourly sleep screen.
if [ ! -f /mnt/us/koreader/koreader.sh ] || [ ! -f /mnt/us/koreader/fridge-run.sh ]; then
    /mnt/us/libkh/bin/fbink -m 'Dashboard files are missing. Complete the installation.'
    exit 1
fi
if pidof luajit >/dev/null 2>&1; then
    /mnt/us/libkh/bin/fbink -m 'KOReader is already running. Quit it before starting the dashboard.'
    exit 0
fi
: > /mnt/us/hava-panosu-enabled
nohup /bin/sh /mnt/us/koreader/fridge-run.sh >> /mnt/us/hava-panosu-launch.log 2>&1 </dev/null &
