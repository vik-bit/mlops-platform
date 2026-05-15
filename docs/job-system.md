| State     | Meaning               |
| --------- | --------------------- |
| PENDING   | waiting for worker    |
| RUNNING   | actively executing    |
| COMPLETED | finished successfully |
| FAILED    | execution failed      |
| RETRYING  | retry attempt running |

{
  "job_id": "uuid",
  "job_type": "training",
  "status": "PENDING",
  "created_at": "...",
  "started_at": "...",
  "completed_at": "...",
  "payload": {},
  "result": {},
  "error": null
}
TRAINING_JOB
BATCH_INFERENCE_JOB
MODEL_EVALUATION_JOB
RETRAINING_JOB

Client Request
      ↓
API Layer
      ↓
Job Created
      ↓
Job Queue
      ↓
Worker Picks Job
      ↓
Execution Starts
      ↓
Metrics + Logs Emitted
      ↓
Job Status Updated
      ↓
Result Stored

Worker should:

execute jobs
update statuses
emit logs
emit metrics
retry failures

Worker should NOT:

expose APIs
store permanent state
handle UI logic