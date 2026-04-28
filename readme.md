# 🚀 MLOps Platform (Mini Vertex AI)

## 📌 Overview

This project is a production-grade MLOps platform inspired by modern machine learning systems. It is designed to replicate the core workflow of platforms like Vertex AI while maintaining a minimal and modular architecture.

The system enables users to:

* Upload and manage datasets
* Train machine learning models asynchronously
* Track experiments and metrics
* Register and deploy models
* Perform real-time and batch inference
* Monitor system and model performance

---

## 🧠 Core Principles

* Modular microservice architecture
* Asynchronous job execution
* Reproducibility via experiment tracking
* Stateless model serving
* Observability-first design

---

## 🏗️ Architecture

```
Frontend (React)
      ↓
API Gateway
      ↓
-----------------------------------------
| Dataset Service                      |
| Training Service                    |
| Deployment Service                  |
| Monitoring Service                  |
-----------------------------------------
      ↓
MLflow (Experiment Tracking & Registry)
      ↓
Docker (Local) → Kubernetes (Planned)
```

---

## ⚙️ Tech Stack

* Backend: FastAPI (Python)
* ML: Scikit-learn, XGBoost
* Experiment Tracking: MLflow
* Frontend: React + TypeScript + Tailwind CSS
* Infra: Docker, Kubernetes (planned)
* Monitoring: Prometheus, Grafana (planned)

---

## 🚀 Getting Started

### 1. Clone the repository

```
git clone <repo-url>
cd mlops-platform
```

### 2. Run services

```
docker-compose up --build
```

### 3. Start MLflow UI

```
mlflow ui
```

---

## 📂 Project Structure

```
backend/        # Microservices
ml/             # ML pipelines
infra/          # Deployment configs
frontend/       # UI dashboard
```

---

## 🎯 Roadmap

* [x] Dataset service
* [x] Training service (basic)
* [ ] Async job system
* [ ] Model registry integration
* [ ] Deployment service (inference APIs)
* [ ] Batch prediction pipeline
* [ ] Monitoring & drift detection
* [ ] Kubernetes deployment
* [ ] RAG integration (Phase 2)

---

## 📌 Vision

To build a scalable, production-grade MLOps platform that mirrors real-world ML systems and evolves into an intelligent AI-driven development environment.

---
