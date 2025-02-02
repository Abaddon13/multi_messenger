#!/bin/bash

# Script for pushing the project's current state to github

notify-send -t 8000 "Multi-messenger simulation sync has been complete!" "Automated backup at $(date)"

cd ~/snakepit/multi_messenger_astro/
git add .
git commit -m "Automated backup: $(date)"
git push
