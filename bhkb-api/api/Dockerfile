FROM python:3.11-slim
WORKDIR /app

# Install system deps for lxml/pypdf if needed
RUN apt-get update && apt-get install -y gcc libxml2-dev libxslt1-dev && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN python - <<'PY'
from pathlib import Path
from tomllib import load

deps = load(open('pyproject.toml', 'rb'))['project']['dependencies']
Path('requirements.txt').write_text('\n'.join(deps))
PY
RUN pip install --no-cache-dir -r requirements.txt && rm requirements.txt

COPY app ./app
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
