# MLOps Platform — Frontend Dashboard

Next.js dashboard for managing datasets, training jobs, model deployments, monitoring, and the AI Copilot. All data flows through the API Gateway at `http://localhost:8000`.

---

## Quick Start

### Prerequisites

- Node.js 18+
- pnpm (recommended) or npm
- Backend services running (`docker compose up` from the project root)

### Installation

```bash
pnpm install
```

Create `.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_POLLING_INTERVAL=5000
```

```bash
pnpm dev
```

Open `http://localhost:3000`.

Sign in as `admin` with the `ADMIN_PASSWORD` set on the API gateway. There is no default password.

---

## How to Use (In-App Guide)

The platform includes a built-in user guide at **How to Use** in the sidebar (or `/how-to-use`).

It covers:

- The five-step workflow: upload → train → deploy → monitor → copilot
- Step-by-step instructions for each section
- Field reference tables for training and drift levels
- An end-to-end Iris classification walkthrough
- Troubleshooting for common errors

Each section includes **Open section** buttons that jump directly to the relevant sidebar view.

---

## Project Structure

```
frontend/vertex-ai-frontend/
├── app/
│   ├── page.tsx            # Main shell with sidebar routing
│   ├── login/page.tsx      # Authentication
│   └── copilot/page.tsx    # AI chat interface
├── components/
│   ├── sidebar.tsx         # Navigation
│   ├── dashboard.tsx       # Overview metrics
│   ├── datasets-view.tsx   # Dataset management
│   ├── training-view.tsx   # Training orchestration
│   ├── deployments-view.tsx# Model serving
│   ├── monitoring-view.tsx # Drift and stats
│   └── profile_modal.tsx   # Dataset analysis modal
├── lib/
│   ├── api.ts              # Gateway API client
│   └── hooks.ts            # Data-fetching hooks
└── .env.local              # API base URL (create this)
```

---

## Development

```bash
pnpm dev          # Development server with HMR
pnpm build        # Production build
pnpm start        # Serve production build
pnpm lint         # ESLint
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Blank dashboard after login | Check `NEXT_PUBLIC_API_BASE_URL` in `.env.local` points to a running gateway |
| Training job stuck on `queued` | Verify Redis is running: `docker compose ps redis` |
| Deploy dropdown empty | Training job must reach `completed` status first |
| Copilot unreachable | Set `GROQ_API_KEY` in root `.env`, restart `ai-service` |
| Charts or stats show "—" | No data yet—complete at least one training job or prediction |
| Session expires unexpectedly | Log in again; tokens expire after the gateway's configured TTL |

---

## API Integration

All frontend requests go through the gateway. See `lib/api.ts` for the full client and `API_INTEGRATION.md` for endpoint details.

Key routes:

```
POST   /login                              # Authentication
GET    /api/datasets/datasets              # List datasets
POST   /api/datasets/datasets              # Upload dataset
POST   /api/training/train                 # Start training
GET    /api/training/jobs                  # List jobs
POST   /api/deployment/deploy/{model_id}   # Deploy model
POST   /api/deployment/predict/{model_id}    # Inference
GET    /api/monitoring/models/{id}/stats   # Model stats
POST   /api/copilot/chat                   # AI Copilot
```

---

## Related Documentation

- [Project README](../../README.md) — Architecture, setup, and v1/v2 roadmap
- [AI Service README](../../backend/ai-service/README.md) — Copilot configuration
- [API Integration Guide](./API_INTEGRATION.md) — Backend endpoint reference
