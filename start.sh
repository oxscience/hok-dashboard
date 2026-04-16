#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
exec gunicorn -w 2 -b 127.0.0.1:5020 "app:create_app()"
