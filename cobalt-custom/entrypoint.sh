#!/bin/sh
# Write cookies from env var to file (if set)
if [ -n "$COOKIES_JSON" ]; then
    echo "$COOKIES_JSON" > /tmp/cookies.json
    export COOKIE_PATH=/tmp/cookies.json
    echo "Cookies loaded from COOKIES_JSON env var"
fi

exec node /app/src/cobalt
