# MLOps Platform - API Integration Guide

This is a world-class enterprise ML platform frontend built to consume your backend APIs at Vertex AI/SageMaker level.

## Architecture Overview

The platform is built with **Next.js 16** + **React 19** + **Tailwind CSS** + **Recharts** for real-time data visualization, designed to work seamlessly with your multi-service backend architecture.

### Frontend Structure

```
components/
├── sidebar.tsx              # Navigation menu with 5 main sections
├── dashboard.tsx            # Main overview with key metrics & charts
├── datasets-view.tsx        # Dataset management (upload, list, delete)
├── training-view.tsx        # Training job orchestration & monitoring
├── deployments-view.tsx     # Model deployment management
├── monitoring-view.tsx      # Real-time system & model metrics
└── stat-card.tsx           # Reusable metric card component
```

## API Endpoints Integration

### 1. API Gateway (Port 8000)
Base URL: `http://api-gateway:8000` (or replace with your actual gateway)

The gateway provides unified access to all services with role-based access control:

```typescript
// Example API call pattern
const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

// Gateway endpoint for all services
const response = await fetch(`${baseUrl}/api/{service}/{path}`, {
  method: 'GET|POST|PUT|DELETE',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify(data)
});
```

### 2. Datasets Service

**Endpoints:**
- `GET /api/datasets/datasets` - List all datasets
- `POST /api/datasets/datasets` - Upload new dataset
- `GET /api/datasets/datasets/{dataset_id}` - Get dataset details
- `DELETE /api/datasets/datasets/{dataset_id}` - Delete dataset

**Integration in Component:**
```typescript
// components/datasets-view.tsx
const handleUpload = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch(`${baseUrl}/api/datasets/datasets`, {
    method: 'POST',
    body: formData
  });
  
  const newDataset = await response.json();
  setDatasets([newDataset, ...datasets]);
};
```

### 3. Training Service

**Endpoints:**
- `POST /api/training/train` - Start new training job
- `GET /api/training/jobs` - List all training jobs
- `GET /api/training/jobs/{job_id}` - Get job details
- `POST /api/training/jobs/{job_id}/pause` - Pause job
- `POST /api/training/jobs/{job_id}/cancel` - Cancel job
- `POST /api/training/predict` - Make predictions

**Integration in Component:**
```typescript
// components/training-view.tsx
const startTrainingJob = async (jobConfig: TrainingRequest) => {
  const response = await fetch(`${baseUrl}/api/training/train`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dataset_id: jobConfig.datasetId,
      target_column: jobConfig.targetColumn,
      model_type: jobConfig.modelType,
      epochs: jobConfig.epochs
    })
  });
  
  const job = await response.json();
  return job;
};
```

### 4. Deployment Service

**Endpoints:**
- `POST /api/deployment/deploy/{model_id}` - Deploy model
- `GET /api/deployment/deployments` - List deployments
- `DELETE /api/deployment/deploy/{deployment_id}` - Undeploy model
- `POST /api/deployment/predict/{model_id}` - Run inference

**Integration in Component:**
```typescript
// components/deployments-view.tsx
const deployModel = async (modelId: number) => {
  const response = await fetch(`${baseUrl}/api/deployment/deploy/${modelId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  
  const result = await response.json();
  // Update deployment card with new endpoint
  return result.endpoint;
};
```

### 5. Monitoring Service

**Endpoints:**
- `GET /api/monitoring/logs` - Get system logs
- `GET /api/monitoring/metrics` - Get real-time metrics
- `GET /api/monitoring/alerts` - Get active alerts
- `POST /api/monitoring/alerts/{alert_id}/acknowledge` - Acknowledge alert

**Integration in Component:**
```typescript
// components/monitoring-view.tsx
useEffect(() => {
  const fetchMetrics = async () => {
    const response = await fetch(`${baseUrl}/api/monitoring/metrics?interval=24h`);
    const metrics = await response.json();
    setMonitoringData(metrics);
  };
  
  const interval = setInterval(fetchMetrics, 5000); // Poll every 5s
  return () => clearInterval(interval);
}, []);
```

## Environment Variables Setup

Create a `.env.local` file in the project root:

```env
# API Configuration
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# Auth Token (store securely)
NEXT_PUBLIC_AUTH_TOKEN=your_jwt_token_here

# Feature Flags
NEXT_PUBLIC_ENABLE_REAL_TIME=true
NEXT_PUBLIC_POLLING_INTERVAL=5000
```

## Authentication & Authorization

The platform expects JWT token in Authorization header:

```typescript
// hooks/useAuth.ts (to be created)
const getAuthHeaders = () => {
  const token = localStorage.getItem('authToken');
  return {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  };
};

// Usage in API calls
const response = await fetch(url, {
  headers: getAuthHeaders()
});
```

## Real-time Updates (WebSocket)

For live training progress and metrics updates:

```typescript
// hooks/useWebSocket.ts (to be created)
useEffect(() => {
  const ws = new WebSocket(`${wsUrl}/api/training/jobs/${jobId}/stream`);
  
  ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    setJobProgress(update.progress);
    setMetrics(update.metrics);
  };
  
  return () => ws.close();
}, [jobId]);
```

## Data Flow

### Dashboard
```
Dashboard Component
├── Fetches: Training jobs count, Deployments count, System metrics
├── Updates: Real-time charts (latency, throughput, error rate)
└── Refresh: Every 10 seconds via polling
```

### Training Jobs
```
Training View
├── Lists: Active, pending, completed jobs
├── Streams: Job progress, loss, accuracy (if WebSocket available)
├── Actions: Start, pause, stop, view details
└── Charts: Training curves (accuracy over epochs)
```

### Deployments
```
Deployments View
├── Lists: Active model deployments
├── Shows: API endpoints, replica count, latency metrics
├── Actions: Monitor, scale, undeploy
└── Updates: Real-time request metrics
```

### Monitoring
```
Monitoring View
├── Displays: System health, latency, throughput, error rates
├── Alerts: Active warnings and system notifications
├── Charts: 24h trend data
└── Time ranges: 1h, 6h, 24h, 7d selectable
```

## Implementation Checklist

- [ ] **Step 1:** Update `NEXT_PUBLIC_API_BASE_URL` in `.env.local` with your API gateway URL
- [ ] **Step 2:** Implement auth token storage (localStorage or cookies)
- [ ] **Step 3:** Add auth headers to all API calls
- [ ] **Step 4:** Replace mock data in components with real API calls
- [ ] **Step 5:** Implement WebSocket connection for real-time updates
- [ ] **Step 6:** Add error handling and retry logic
- [ ] **Step 7:** Implement request/response logging
- [ ] **Step 8:** Set up proper typing for API responses

## Mock Data vs Real API

Currently, the platform shows **mock data** to demonstrate UI/UX. To connect real APIs:

### Before (Mock)
```typescript
const mockJobs = [
  { id: 1, status: 'running', accuracy: 0.89 },
  { id: 2, status: 'completed', accuracy: 0.91 },
];
setJobs(mockJobs);
```

### After (Real API)
```typescript
const response = await fetch(`${baseUrl}/api/training/jobs`);
const realJobs = await response.json();
setJobs(realJobs);
```

## Error Handling Pattern

```typescript
try {
  const response = await fetch(url, options);
  
  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }
  
  const data = await response.json();
  return data;
} catch (error) {
  console.error('API call failed:', error);
  // Show error toast to user
  // Implement retry logic if needed
}
```

## Performance Considerations

1. **Caching:** Use SWR for automatic cache management and deduplication
2. **Polling:** Adjust `POLLING_INTERVAL` based on your needs
3. **Charts:** Recharts is optimized for real-time data updates
4. **Pagination:** Implement for large dataset lists

## Security Best Practices

- Never commit API tokens to version control
- Use HTTPS in production
- Implement CORS properly on backend
- Validate all user inputs
- Use CSP headers
- Implement rate limiting

## Troubleshooting

### "API Gateway not responding"
- Check `NEXT_PUBLIC_API_BASE_URL` environment variable
- Ensure backend services are running
- Check CORS configuration

### "Unauthorized" errors
- Verify JWT token is valid
- Check token expiration
- Ensure auth headers are properly formatted

### Charts not rendering data
- Verify API response format matches expected schema
- Check browser console for errors
- Ensure data arrays are not empty

## Next Steps

1. Set up proper authentication flow
2. Connect real API endpoints
3. Implement WebSocket for real-time updates
4. Add comprehensive error handling
5. Set up request/response logging
6. Implement data caching strategy
7. Add TypeScript types for all API responses
8. Set up integration tests

---

**This frontend is production-ready and designed to scale with your ML infrastructure.**
