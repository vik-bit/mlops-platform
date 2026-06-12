# MLOps Platform - Enterprise ML Management Dashboard

A world-class frontend dashboard built with **Next.js 16**, **React 19**, and **Tailwind CSS** for managing, training, deploying, and monitoring machine learning models at enterprise scale.

## 🎯 Features

### 📊 Dashboard
- **Key Metrics**: Training jobs, completed models, active deployments, system latency
- **Real-time Charts**: Request latency and throughput visualization
- **System Health**: API Gateway, Database, Training Service, Deployment Service status
- **Recent Activity**: Latest training jobs and deployment updates

### 📁 Dataset Management
- **Upload Interface**: Drag-and-drop support for CSV, JSON, Parquet files
- **Dataset Registry**: Complete list of available training datasets
- **Metadata Tracking**: File size, row count, upload timestamp
- **Quick Actions**: Download, preview, delete datasets

### 🧠 Training Jobs
- **Job Orchestration**: Create and manage ML training pipelines
- **Progress Tracking**: Real-time accuracy and loss metrics
- **Epoch Visualization**: Training curves showing model improvement
- **Job Control**: Start, pause, stop training operations
- **Status Indicators**: Running, completed, pending, failed states

### ⚡ Deployments
- **Model Deployment**: Deploy trained models to production
- **Endpoint Management**: Unique API endpoints for each model
- **Resource Metrics**: CPU, memory, replica count monitoring
- **Performance Data**: Request volume, latency, error rates
- **Scaling Controls**: Adjust replica counts on demand

### 📈 Monitoring & Alerts
- **System Metrics**: Latency, throughput, error rate, uptime
- **Time Range Selection**: 1h, 6h, 24h, 7d views
- **Alert System**: Active warnings for anomalies
- **Resource Usage**: CPU and memory utilization trends
- **Health Dashboard**: Real-time system status

## 🏗 Architecture

```
Frontend (Next.js 16)
    ↓
API Gateway (FastAPI)
    ├─ Training Service
    ├─ Dataset Service
    ├─ Deployment Service
    └─ Monitoring Service
```

## 🚀 Quick Start

### Prerequisites
- Node.js 18+
- pnpm (recommended) or npm

### Installation

```bash
# Install dependencies
pnpm install

# Start development server
pnpm dev

# Open browser
# http://localhost:3000
```

### Environment Setup

Create `.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_POLLING_INTERVAL=5000
```

See `API_INTEGRATION.md` for detailed API integration guide.

## 📚 Project Structure

```
├── app/
│   ├── layout.tsx          # Root layout with theme setup
│   ├── page.tsx            # Main dashboard router
│   └── globals.css         # Design tokens & styles
├── components/
│   ├── sidebar.tsx         # Navigation menu
│   ├── dashboard.tsx       # Main overview
│   ├── datasets-view.tsx   # Dataset management
│   ├── training-view.tsx   # Training orchestration
│   ├── deployments-view.tsx # Model deployments
│   ├── monitoring-view.tsx # System monitoring
│   └── stat-card.tsx       # Metric card component
├── lib/
│   └── utils.ts            # Tailwind utilities
└── API_INTEGRATION.md      # Backend integration guide
```

## 🎨 Design System

### Color Palette
- **Primary**: #3b82f6 (Blue) - Main actions, navigation
- **Accent**: #06b6d4 (Cyan) - Highlights, important metrics
- **Success**: #10b981 (Green) - Positive states
- **Warning**: #f59e0b (Orange) - Cautions
- **Error**: #ef4444 (Red) - Critical states
- **Background**: #0a0e27 (Dark Navy) - Main surface
- **Card**: #121829 (Darker Navy) - Elevated surfaces

### Typography
- **Headings**: Geist Sans (Bold)
- **Body**: Geist Sans (Regular)
- **Code**: Geist Mono (Monospace)

## 🔗 API Integration

All components are prepared to consume your backend APIs:

### Key Endpoints

```
POST   /api/datasets/datasets              # Upload dataset
GET    /api/datasets/datasets              # List datasets
DELETE /api/datasets/datasets/{id}         # Delete dataset

POST   /api/training/train                 # Start training job
GET    /api/training/jobs                  # List jobs
GET    /api/training/jobs/{id}             # Job details
POST   /api/training/predict               # Make predictions

POST   /api/deployment/deploy/{id}         # Deploy model
GET    /api/deployment/deployments         # List deployments
DELETE /api/deployment/deploy/{id}         # Undeploy model

GET    /api/monitoring/metrics             # System metrics
GET    /api/monitoring/alerts              # Active alerts
```

See `API_INTEGRATION.md` for complete integration guide.

## 🔐 Authentication

The platform supports JWT-based authentication:

```typescript
// Add to all API requests
headers: {
  'Authorization': `Bearer ${token}`,
  'Content-Type': 'application/json'
}
```

## 📊 Charts & Visualizations

Built with **Recharts** for smooth, responsive real-time data:
- Area charts for latency trends
- Bar charts for throughput
- Line charts for training metrics
- Composed charts for multi-metric comparison

## 🧪 Development

### Available Scripts

```bash
# Development server with HMR
pnpm dev

# Production build
pnpm build
pnpm start

# Lint code
pnpm lint

# Type check
pnpm type-check
```

### Component Development

Components use:
- **React 19** hooks (useState, useEffect)
- **Tailwind CSS** for styling
- **Lucide Icons** for UI icons
- **Recharts** for data visualization

## 📱 Responsive Design

- Mobile-first approach
- Tested on 375px (mobile) to 1920px (desktop)
- Sidebar collapses on small screens
- Charts scale responsively
- Touch-friendly controls

## ⚡ Performance

- **Optimized Charts**: Memoized Recharts components
- **Lazy Loading**: Route-based code splitting
- **Image Optimization**: Next.js Image component ready
- **Caching**: SWR pattern ready for implementation

## 🛡 Security Features

- Environment variable protection
- CORS-ready architecture
- XSS prevention with React escaping
- CSRF token support ready
- Input validation patterns

## 🐛 Troubleshooting

### Charts not displaying
- Verify API response data format
- Check browser console for errors
- Ensure data arrays contain values

### API calls failing
- Check `NEXT_PUBLIC_API_BASE_URL` environment variable
- Verify backend services are running
- Check CORS configuration
- Validate authentication token

### Styling issues
- Clear Next.js cache: `rm -rf .next`
- Restart dev server
- Check Tailwind CSS imports

## 📖 Documentation

- **API Integration**: See `API_INTEGRATION.md`
- **Tailwind Config**: See `tailwind.config.ts`
- **Component Patterns**: View individual component files

## 🚢 Deployment

### Vercel (Recommended)
```bash
vercel deploy
```

### Docker
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY . .
RUN pnpm install
RUN pnpm build
EXPOSE 3000
CMD ["pnpm", "start"]
```

### Environment Variables
Set in your deployment platform:
- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_WS_URL`
- `NEXT_PUBLIC_POLLING_INTERVAL`

## 📈 Metrics & Monitoring

The dashboard displays real-time metrics:
- Request latency (ms)
- Throughput (requests/day)
- Error rate (%)
- System uptime (%)
- Model accuracy (%)
- Training loss curves

## 🤝 Contributing

This is a starter template. To extend:

1. Add new components in `/components`
2. Create API hooks in `/hooks` (to be created)
3. Update types in `/types` (to be created)
4. Add new routes in `/app`

## 📝 License

Built with v0.app - Available under MIT License

## 🎓 Learning Resources

- [Next.js Docs](https://nextjs.org/docs)
- [React Docs](https://react.dev)
- [Tailwind CSS](https://tailwindcss.com)
- [Recharts](https://recharts.org)
- [Lucide Icons](https://lucide.dev)

---

**Ready to connect to your ML backend! See `API_INTEGRATION.md` to get started.**
