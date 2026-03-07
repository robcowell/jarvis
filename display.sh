#!/bin/bash

export DISPLAY=:0
export XAUTHORITY=/home/robcowell/.Xauthority

pkill chromium 2>/dev/null

sleep 2

chromium \
  --kiosk http://localhost:5000 \
  --force-device-scale-factor=0.85 \
  --password-store=basic \
  --no-first-run \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=TranslateUI \
  --disable-restore-session-state \
  --overscroll-history-navigation=0 \
  --noerrdialogs \
  --incognito \
  &
