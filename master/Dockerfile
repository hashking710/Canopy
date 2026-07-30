FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY canopy_master ./canopy_master

RUN pip install --no-cache-dir .

EXPOSE 9100

CMD ["uvicorn", "canopy_master.main:app", "--host", "0.0.0.0", "--port", "9100"]
