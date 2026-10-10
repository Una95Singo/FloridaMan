FROM node:22-bookworm-slim AS web
WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build
FROM python:3.12-slim
WORKDIR /app
COPY requirements-v2.txt ./
RUN pip install --no-cache-dir -r requirements-v2.txt
COPY server/ ./server/
COPY floridaman/ ./floridaman/
COPY --from=web /app/web/dist ./web/dist
RUN useradd --create-home --uid 10001 floridaman
USER floridaman
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
