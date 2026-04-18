FROM python:3.12-slim

WORKDIR /app

# Install runtime deps from pyproject.toml (single source of truth).
COPY pyproject.toml README.md ./
COPY cocos/ cocos/
COPY server.py run.sh ./
RUN pip install --no-cache-dir . && chmod +x run.sh

# MCP server runs on stdio, no port needed
CMD ["python", "server.py"]
