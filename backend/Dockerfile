FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# install dependencies
COPY ./backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# copy backend application
COPY ./backend /app

# copy frontend files to root level for access
COPY ./frontend /frontend

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
