'use client'

import type { ElementType, ReactNode } from 'react'
import {
  BookOpen,
  LogIn,
  Database,
  Brain,
  Zap,
  BarChart3,
  Sparkles,
  ArrowRight,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'

interface HowToUseViewProps {
  onNavigate?: (view: string) => void
}

const WORKFLOW = [
  { step: 1, label: 'Upload dataset', view: 'datasets', icon: Database },
  { step: 2, label: 'Train model', view: 'training', icon: Brain },
  { step: 3, label: 'Deploy', view: 'deployments', icon: Zap },
  { step: 4, label: 'Monitor', view: 'monitoring', icon: BarChart3 },
  { step: 5, label: 'Ask Copilot', view: 'copilot', icon: Sparkles },
]

const TOC = [
  { id: 'overview', label: 'Overview' },
  { id: 'sign-in', label: 'Sign in' },
  { id: 'datasets', label: 'Datasets' },
  { id: 'training', label: 'Training jobs' },
  { id: 'deployments', label: 'Deployments' },
  { id: 'monitoring', label: 'Monitoring' },
  { id: 'copilot', label: 'AI Copilot' },
  { id: 'example', label: 'End-to-end example' },
  { id: 'troubleshooting', label: 'Troubleshooting' },
]

function Section({
  id,
  icon: Icon,
  title,
  children,
  view,
  onNavigate,
}: {
  id: string
  icon: ElementType
  title: string
  children: ReactNode
  view?: string
  onNavigate?: (view: string) => void
}) {
  return (
    <section id={id} className="scroll-mt-24">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
            <Icon className="w-4.5 h-4.5 text-primary" />
          </div>
          <h2 className="text-xl font-semibold text-foreground">{title}</h2>
        </div>
        {view && onNavigate && (
          <Button variant="outline" size="sm" onClick={() => onNavigate(view)}>
            Open section
            <ArrowRight className="w-3.5 h-3.5 ml-1" />
          </Button>
        )}
      </div>
      <div className="pl-12 space-y-4 text-sm text-foreground leading-relaxed">{children}</div>
    </section>
  )
}

function StepList({ items }: { items: string[] }) {
  return (
    <ol className="space-y-2 list-none counter-reset-none">
      {items.map((item, i) => (
        <li key={i} className="flex gap-3">
          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-secondary text-xs font-semibold flex items-center justify-center text-muted-foreground">
            {i + 1}
          </span>
          <span className="pt-0.5">{item}</span>
        </li>
      ))}
    </ol>
  )
}

function InfoTable({ rows }: { rows: { label: string; detail: string }[] }) {
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.label} className={i % 2 === 0 ? 'bg-secondary/40' : 'bg-white'}>
              <td className="px-4 py-2.5 font-medium text-foreground w-1/3 border-r border-border">
                {row.label}
              </td>
              <td className="px-4 py-2.5 text-muted-foreground">{row.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Tip({ children }: { children: ReactNode }) {
  return (
    <div className="flex gap-2.5 p-3.5 rounded-lg bg-blue-50 border border-blue-100 text-sm text-blue-900">
      <CheckCircle2 className="w-4 h-4 flex-shrink-0 mt-0.5 text-blue-600" />
      <div>{children}</div>
    </div>
  )
}

function Warning({ children }: { children: ReactNode }) {
  return (
    <div className="flex gap-2.5 p-3.5 rounded-lg bg-amber-50 border border-amber-100 text-sm text-amber-900">
      <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-amber-600" />
      <div>{children}</div>
    </div>
  )
}

export default function HowToUseView({ onNavigate }: HowToUseViewProps) {
  return (
    <div className="flex-1 overflow-auto bg-white">
      {/* Header */}
      <div className="border-b border-border bg-white sticky top-0 z-10">
        <div className="px-8 py-6">
          <div className="flex items-center gap-3 mb-1">
            <BookOpen className="w-7 h-7 text-primary" />
            <h1 className="text-3xl font-bold text-foreground">How to Use</h1>
          </div>
          <p className="text-muted-foreground mt-1">
            Step-by-step guide to upload data, train a model, deploy it, and monitor predictions.
            No prior MLOps experience required.
          </p>
        </div>
      </div>

      <div className="p-8">
        {/* Workflow strip */}
        <div id="overview" className="scroll-mt-24 mb-10">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
            The workflow
          </h2>
          <div className="flex flex-wrap items-center gap-2">
            {WORKFLOW.map((item, i) => {
              const Icon = item.icon
              return (
                <div key={item.step} className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onNavigate?.(item.view)}
                    disabled={!onNavigate}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition ${
                      onNavigate
                        ? 'border-border hover:border-primary hover:bg-primary/5 cursor-pointer'
                        : 'border-border cursor-default'
                    }`}
                  >
                    <span className="w-5 h-5 rounded-full bg-primary text-white text-xs flex items-center justify-center">
                      {item.step}
                    </span>
                    <Icon className="w-4 h-4 text-muted-foreground" />
                    {item.label}
                  </button>
                  {i < WORKFLOW.length - 1 && (
                    <ChevronRight className="w-4 h-4 text-muted-foreground hidden sm:block" />
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Table of contents */}
        <nav className="mb-10 p-4 rounded-xl border border-border bg-secondary/30">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
            On this page
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {TOC.map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                className="text-sm text-primary hover:underline"
              >
                {item.label}
              </a>
            ))}
          </div>
        </nav>

        <div className="space-y-12">
          <Section id="sign-in" icon={LogIn} title="Sign in">
            <StepList
              items={[
                'Open the platform URL. If you are not signed in, you are redirected to the login page.',
                'Enter your username and password, then click Sign In.',
                'On success, you land on the Dashboard with a summary of jobs and deployments.',
              ]}
            />
            <Warning>
              There is no default password. The <code className="font-mono bg-white/60 px-1 rounded">admin</code> account
              uses the <code className="font-mono bg-white/60 px-1 rounded">ADMIN_PASSWORD</code> set on the API gateway.
            </Warning>
          </Section>

          <Section
            id="datasets"
            icon={Database}
            title="Upload and analyze a dataset"
            view="datasets"
            onNavigate={onNavigate}
          >
            <StepList
              items={[
                'Go to Datasets in the sidebar.',
                'Click Upload Dataset or Select Files in the upload zone.',
                'Choose one or more CSV files and click Upload Files.',
                'Once uploaded, click Analyze on a row to inspect column types, missing values, and statistics.',
                'Select a target column — the field you want the model to predict. Note the exact column name for training.',
              ]}
            />
            <Tip>Review the profile before training. Wrong target columns are the most common cause of failed jobs.</Tip>
          </Section>

          <Section
            id="training"
            icon={Brain}
            title="Train a model"
            view="training"
            onNavigate={onNavigate}
          >
            <StepList
              items={[
                'Go to Training Jobs and click New Training Job.',
                'Select your dataset, enter the target column name, and choose Classification or Regression.',
                'Pick a model type. Random Forest is a reliable default for tabular CSV data.',
                'Adjust hyperparameters if needed, or leave defaults.',
                'Click Start Training and wait for status to change from queued → running → completed.',
              ]}
            />
            <InfoTable
              rows={[
                { label: 'Dataset', detail: 'The CSV you uploaded in the previous step' },
                { label: 'Target column', detail: 'Column to predict (must match Analyze step exactly)' },
                { label: 'Task type', detail: 'Classification for categories; Regression for numbers' },
                { label: 'Model type', detail: 'Algorithm — Random Forest, XGBoost, LightGBM, etc.' },
              ]}
            />
            <p className="text-muted-foreground">
              Completed jobs show accuracy (classification) or R² (regression). Metrics are also logged to MLflow at{' '}
              <code className="font-mono text-xs bg-secondary px-1.5 py-0.5 rounded">localhost:5000</code>.
            </p>
          </Section>

          <Section
            id="deployments"
            icon={Zap}
            title="Deploy and run predictions"
            view="deployments"
            onNavigate={onNavigate}
          >
            <StepList
              items={[
                'Go to Deployments and click Deploy Model.',
                'Select a completed training job from the dropdown and confirm.',
                'When status shows active, copy the API endpoint or expand the card to test in the UI.',
                'Click Predict / Explain, fill in feature values matching the model schema, and run a prediction.',
                'Use Explain (SHAP) to see which features drove the result.',
              ]}
            />
            <Tip>
              Batch predictions: expand a deployment, upload a CSV with the same feature columns, and click Run Batch.
            </Tip>
          </Section>

          <Section
            id="monitoring"
            icon={BarChart3}
            title="Monitor production models"
            view="monitoring"
            onNavigate={onNavigate}
          >
            <StepList
              items={[
                'Go to Monitoring to see stats for each deployed model.',
                'Review total predictions, average latency, and success rate.',
                'Expand Prediction History to inspect recent inputs and outputs.',
                'Expand Drift Analysis to check whether incoming data differs from training data.',
              ]}
            />
            <InfoTable
              rows={[
                { label: 'none', detail: 'No significant drift — no action needed' },
                { label: 'moderate', detail: 'Review recent predictions; consider retraining with fresh data' },
                { label: 'high', detail: 'Retrain and redeploy — input distribution has shifted significantly' },
              ]}
            />
          </Section>

          <Section
            id="copilot"
            icon={Sparkles}
            title="Use the AI Copilot"
            view="copilot"
            onNavigate={onNavigate}
          >
            <p>
              The Copilot answers questions by querying live platform data — training jobs, deployments,
              MLflow runs, Prometheus metrics, and drift reports. It does not guess from static knowledge.
            </p>
            <div className="p-4 rounded-lg bg-secondary/50 border border-border font-mono text-xs space-y-1.5 text-foreground">
              <p>&quot;What training jobs completed today?&quot;</p>
              <p>&quot;Which models are currently deployed?&quot;</p>
              <p>&quot;Compare training jobs 1 and 2&quot;</p>
              <p>&quot;Is model 3 experiencing data drift?&quot;</p>
              <p>&quot;What is the average prediction latency?&quot;</p>
            </div>
            <Warning>
              The Copilot requires a Groq API key configured in the backend <code className="font-mono bg-white/60 px-1 rounded">.env</code> file.
              If you see connection errors, verify the AI service is running.
            </Warning>
          </Section>

          <Section id="example" icon={BookOpen} title="End-to-end example: Iris classification">
            <StepList
              items={[
                'Upload backend/training-service/datasets/Iris.csv from the Datasets page.',
                'Analyze the file and set the target column to species.',
                'Start a Classification job with Random Forest on that dataset.',
                'Wait for completed status (typically 95%+ accuracy).',
                'Deploy the model from the Deployments page.',
                'Enter sepal and petal measurements in the Predict panel and verify the species output.',
                'Check Monitoring for prediction history, then ask the Copilot: "What accuracy did the Iris model achieve?"',
              ]}
            />
          </Section>

          <Section id="troubleshooting" icon={AlertCircle} title="Troubleshooting">
            <InfoTable
              rows={[
                {
                  label: 'Cannot sign in',
                  detail: 'Confirm docker compose up is running and NEXT_PUBLIC_API_BASE_URL points to localhost:8000',
                },
                {
                  label: 'Training stuck on queued',
                  detail: 'Check that Redis is running: docker compose ps redis',
                },
                {
                  label: 'Deploy dropdown is empty',
                  detail: 'The training job must reach completed status before a model can be deployed',
                },
                {
                  label: 'Copilot returns errors',
                  detail: 'Set GROQ_API_KEY in the project root .env and restart the ai-service container',
                },
                {
                  label: 'Dashboard shows dashes',
                  detail: 'No data yet — complete at least one training job or prediction first',
                },
              ]}
            />
          </Section>
        </div>
      </div>
    </div>
  )
}
