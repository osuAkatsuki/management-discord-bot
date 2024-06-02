#!/usr/bin/env bash
set -eo pipefail

if [ -z "$APP_ENV" ]; then
  echo "Please set APP_ENV"
  exit 1
fi

if [ -z "$APP_COMPONENT" ]; then
  echo "Please set APP_COMPONENT"
  exit 1
fi

if [[ $PULL_SECRETS_FROM_VAULT -eq 1 ]]; then
  echo "Fetching secrets from vault"
  akatsuki vault get score-service $APP_ENV -o .env
  echo "Fetched secrets from vault"
  source .env
  echo "Sourced secrets from vault"
fi

cd /srv/root

# await connected service availability
/scripts/await-service.sh $READ_DB_HOST $READ_DB_PORT $SERVICE_READINESS_TIMEOUT
/scripts/await-service.sh $WRITE_DB_HOST $WRITE_DB_PORT $SERVICE_READINESS_TIMEOUT

# ensure database exists
/scripts/init-db.sh

# run sql database migrations & seeds
/scripts/migrate-db.sh up
# /scripts/seed-db.sh up

exec app/main.py
