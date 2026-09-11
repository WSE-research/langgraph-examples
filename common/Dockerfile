# Image of the Pizza API (main.py), deployed at https://wse-research.org/pizza-api
#
# Python 3.12: the previous base image was python:3.9-slim, on which the build
# stopped working -- the unpinned spacy in requirements.txt resolves to a
# version whose thinc dependency requires Python >= 3.10, so pip could not
# satisfy it and every rebuild failed. The service itself only needs FastAPI
# and uvicorn, so it installs requirements-service.txt and leaves the
# dependencies of the example scripts out of the image entirely. That also
# removes the need for a compiler in the image.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements-service.txt .
RUN pip install --no-cache-dir -r requirements-service.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
