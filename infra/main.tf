terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

resource "docker_network" "app_network" {
  name = "receipts_rag_network"
}

resource "docker_image" "backend" {
  name         = "receipts-ocr-rag-backend:latest"
  keep_locally = true
  build {
    context    = "${path.module}/../backend"
    dockerfile = "Dockerfile"
  }
}

resource "docker_image" "frontend" {
  name         = "receipts-ocr-rag-frontend:latest"
  keep_locally = true
  build {
    context    = "${path.module}/../frontend"
    dockerfile = "Dockerfile"
  }
}

resource "docker_container" "backend" {
  name  = "receipts-ocr-rag-backend"
  image = docker_image.backend.image_id
  networks_advanced {
    name = docker_network.app_network.name
  }
  ports {
    internal = 5001
    external = 5001
  }
  volumes {
    host_path      = "${path.module}/../data"
    container_path = "/app/data"
  }
  volumes {
    host_path      = "${path.module}/../models"
    container_path = "/app/models"
  }
  env = [
    "DB_PATH=/app/data/scans.db",
    "OPENRAG_MODEL_PATH=/app/models",
    "DEEPSEEK_HARNESS_PLUGINS=database,web"
  ]
  healthcheck {
    test     = ["CMD", "curl", "-f", "http://localhost:5001/health"]
    interval = "30s"
    timeout  = "10s"
    retries  = 5
  }
  restart = "unless-stopped"
}

resource "docker_container" "frontend" {
  name  = "receipts-ocr-rag-frontend"
  image = docker_image.frontend.image_id
  networks_advanced {
    name = docker_network.app_network.name
  }
  ports {
    internal = 5173
    external = 5173
  }
  env = [
    "VITE_BACKEND_URL=http://backend:5001"
  ]
  depends_on = [docker_container.backend]
  restart     = "unless-stopped"
}
