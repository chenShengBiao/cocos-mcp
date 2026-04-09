FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY cocos/ cocos/
COPY server.py run.sh ./
RUN chmod +x run.sh

# MCP server runs on stdio, no port needed
CMD ["python", "server.py"]
