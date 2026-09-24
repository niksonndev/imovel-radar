# syntax=docker/dockerfile:1
# Build context: raiz do monorepo
#   docker build -f apps/whatsapp-bot/Dockerfile .

FROM rust:1-bookworm AS builder
WORKDIR /src
COPY apps/whatsapp-bot/Cargo.toml apps/whatsapp-bot/Cargo.lock ./
COPY apps/whatsapp-bot/src ./src
RUN cargo build --release --locked

FROM debian:bookworm-slim AS runner
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates libpq5 gosu \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 1001 --create-home app
COPY --from=builder /src/target/release/whatsapp-bot /usr/local/bin/whatsapp-bot
COPY apps/whatsapp-bot/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENV PORT=10000 \
    WHATSAPP_SESSION_PATH=/data/whatsapp.db
EXPOSE 10000
ENTRYPOINT ["/entrypoint.sh"]
