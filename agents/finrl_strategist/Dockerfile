FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install poetry && poetry install --no-root
COPY . /app
CMD ["python", "-m", "agents.finrl_strategist"]
