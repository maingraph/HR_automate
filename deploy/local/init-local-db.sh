#!/bin/sh
set -eu

for migration in /migrations/*.sql; do
  if [ "$(basename "$migration")" = "001_core.sql" ]; then
    sed \
      -e '/create extension if not exists vector;/d' \
      -e 's/embedding vector(768)/embedding double precision[]/' \
      -e '/create index if not exists candidates_embedding_idx/,/with (lists = 100);/d' \
      -e '/create or replace function public.match_candidates(/,/^\$\$;/d' \
      "$migration" | psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"
  else
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --file "$migration"
  fi
done
