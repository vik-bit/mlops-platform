from prometheus_client import Counter, Histogram, Gauge
import time
import psutil

# Total prediction requests
prediction_counter = Counter(
    "prediction_requests_total",
    "Total number of prediction requests"
)

# Failed prediction requests
prediction_failures = Counter(
    "prediction_failures_total",
    "Total failed predictions"
)

# Prediction latency
prediction_latency = Histogram(
    "prediction_latency_seconds",
    "Prediction latency in seconds"
)

# Active memory usage
memory_usage = Gauge(
    "memory_usage_percent",
    "System memory usage percent"
)

# CPU usage
cpu_usage = Gauge(
    "cpu_usage_percent",
    "CPU usage percent"
)

def update_system_metrics():
    memory_usage.set(psutil.virtual_memory().percent)
    cpu_usage.set(psutil.cpu_percent())

class MonitorPrediction:
    def __enter__(self):
        self.start_time = time.time()
        prediction_counter.inc()

    def __exit__(self, exc_type, exc_val, exc_tb):
        latency = time.time() - self.start_time
        prediction_latency.observe(latency)

        if exc_type:
            prediction_failures.inc()

        update_system_metrics()