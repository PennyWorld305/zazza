# Deploy instructions (Ubuntu 24.04 LTS)

This document explains how to prepare a fresh Ubuntu 24.04 server and deploy the project using Docker Compose.

Overview:
- Install Docker and Docker Compose (plugin)
- Clone repository on the server
- Copy `backend/.env.example` to `backend/.env` and fill secrets
- Run `docker compose up -d`

1) Prepare Ubuntu (run as root or with sudo):

```bash
apt update && apt upgrade -y
apt install -y ca-certificates curl gnupg lsb-release

# Install Docker
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add your user to the docker group (optional)
usermod -aG docker $USER
```

2) Clone project and prepare env:

```bash
cd /srv
git clone https://gitlab.com/vladellave/zaza.git
cd zaza/backend
cp .env.example .env
# Edit .env: set SECRET_KEY to a secure random value and adjust DATABASE_URL if needed
```

3) Start with Docker Compose (from repository root):

```bash
cd /srv/zaza
docker compose up -d --build
```

4) Verify services:

```bash
docker compose ps
docker compose logs -f web
```

Notes:
- By default the compose file creates a Postgres service. If you already have an external DB, set `DATABASE_URL` in `backend/.env` to point to it and remove or disable the `db` service in `docker-compose.yml`.
- When you add a domain later, update `deploy/nginx/default.conf` and reload nginx container or replace with an nginx image built from a Dockerfile including certbot, or use a separate Let's Encrypt container.
