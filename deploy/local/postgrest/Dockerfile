FROM python:3.11-slim-bookworm

ARG TARGETARCH
ARG POSTGREST_VERSION=v14.14

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl libpq5 xz-utils \
    && case "$TARGETARCH" in \
         amd64) asset="postgrest-${POSTGREST_VERSION}-linux-static-x86-64.tar.xz" ;; \
         arm64) asset="postgrest-${POSTGREST_VERSION}-ubuntu-aarch64.tar.xz" ;; \
         *) echo "Unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
       esac \
    && curl --fail --location --retry 5 \
       "https://github.com/PostgREST/postgrest/releases/download/${POSTGREST_VERSION}/${asset}" \
       | tar -xJ -C /usr/local/bin \
    && postgrest --version \
    && apt-get purge -y --auto-remove curl xz-utils \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 3000
ENTRYPOINT ["postgrest"]
