# Shadow-only image. No secrets, Telegram publishing or Hermes runtime are baked in.
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --gid 10001 radar && useradd --uid 10001 --gid 10001 --home-dir /app --no-create-home radar
COPY --chown=10001:10001 news_radar.py trending_radar.py channel_digest.py cambodia_brief.py ./
COPY --chown=10001:10001 config/ ./config/
RUN mkdir -p /app/state /app/out && chown -R 10001:10001 /app/state /app/out
USER 10001:10001
ENTRYPOINT ["python"]
CMD ["cambodia_brief.py", "--dry-run", "--test-mode"]
