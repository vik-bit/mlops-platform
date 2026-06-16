'use client';

import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';
import React from 'react';

// ─── Card ────────────────────────────────────────────────
export function Card({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-xl',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('px-5 py-4 border-b border-[hsl(var(--border))]', className)} {...props}>
      {children}
    </div>
  );
}

export function CardContent({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('px-5 py-4', className)} {...props}>
      {children}
    </div>
  );
}

// ─── Stat Card ───────────────────────────────────────────
interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: string;
  trendUp?: boolean;
  color?: 'green' | 'blue' | 'amber' | 'red' | 'purple';
}

const colorMap = {
  green: 'hsl(var(--green))',
  blue: 'hsl(var(--blue))',
  amber: 'hsl(var(--amber))',
  red: 'hsl(var(--red))',
  purple: 'hsl(var(--purple))',
};

export function StatCard({ title, value, icon, trend, trendUp, color = 'green' }: StatCardProps) {
  const c = colorMap[color];
  return (
    <div
      className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-xl p-5 relative overflow-hidden"
      style={{ '--stat-color': c } as React.CSSProperties}
    >
      <div
        className="absolute top-0 right-0 w-24 h-24 rounded-full blur-3xl opacity-5"
        style={{ background: c, transform: 'translate(30%, -30%)' }}
      />
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-widest text-[hsl(var(--muted-foreground))] mb-3">
            {title}
          </p>
          <p className="text-2xl font-bold font-display" style={{ color: c }}>
            {value}
          </p>
          {trend && (
            <p className={cn('text-[11px] mt-1', trendUp ? 'text-[hsl(var(--green))]' : 'text-[hsl(var(--muted-foreground))]')}>
              {trend}
            </p>
          )}
        </div>
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: `color-mix(in srgb, ${c} 12%, transparent)`, border: `1px solid color-mix(in srgb, ${c} 20%, transparent)` }}
        >
          <span style={{ color: c }}>{icon}</span>
        </div>
      </div>
    </div>
  );
}

// ─── Badge ───────────────────────────────────────────────
interface BadgeProps {
  variant?: string;
  children: React.ReactNode;
  className?: string;
}

export function Badge({ variant = 'default', children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium font-mono',
        `badge-${variant}`,
        className
      )}
    >
      {children}
    </span>
  );
}

// ─── Button ──────────────────────────────────────────────
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: React.ReactNode;
}

const btnVariants = {
  primary: 'bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:bg-[hsl(var(--primary)/0.85)] shadow-[0_0_12px_hsl(var(--primary)/0.25)]',
  secondary: 'bg-[hsl(var(--secondary))] text-[hsl(var(--secondary-foreground))] hover:bg-[hsl(220_12%_18%)]',
  ghost: 'bg-transparent text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--accent))] hover:text-[hsl(var(--foreground))]',
  danger: 'bg-[hsl(var(--destructive)/0.12)] text-[hsl(var(--destructive))] hover:bg-[hsl(var(--destructive)/0.2)] border border-[hsl(var(--destructive)/0.2)]',
  outline: 'bg-transparent border border-[hsl(var(--border))] text-[hsl(var(--foreground))] hover:bg-[hsl(var(--accent))]',
};

const btnSizes = {
  sm: 'h-7 px-3 text-[12px] gap-1.5',
  md: 'h-9 px-4 text-[13px] gap-2',
  lg: 'h-11 px-5 text-[14px] gap-2',
};

export function Button({
  variant = 'secondary',
  size = 'md',
  loading,
  icon,
  children,
  className,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed',
        btnVariants[variant],
        btnSizes[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 size={13} className="animate-spin" /> : icon}
      {children}
    </button>
  );
}

// ─── Input ───────────────────────────────────────────────
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
}

export function Input({ label, error, icon, className, ...props }: InputProps) {
  return (
    <div className="space-y-1.5">
      {label && (
        <label className="block text-[12px] font-medium text-[hsl(var(--muted-foreground))] uppercase tracking-wider">
          {label}
        </label>
      )}
      <div className="relative">
        {icon && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[hsl(var(--muted-foreground))]">
            {icon}
          </span>
        )}
        <input
          className={cn(
            'w-full h-9 bg-[hsl(var(--secondary))] border border-[hsl(var(--border))] rounded-lg text-[13px] text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground)/0.5)]',
            'focus:outline-none focus:border-[hsl(var(--primary)/0.5)] focus:ring-1 focus:ring-[hsl(var(--primary)/0.2)]',
            'transition-all duration-150',
            icon ? 'pl-9 pr-3' : 'px-3',
            error && 'border-[hsl(var(--destructive)/0.5)]',
            className
          )}
          {...props}
        />
      </div>
      {error && <p className="text-[11px] text-[hsl(var(--destructive))]">{error}</p>}
    </div>
  );
}

// ─── Select ──────────────────────────────────────────────
interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: { value: string; label: string }[];
}

export function Select({ label, options, className, ...props }: SelectProps) {
  return (
    <div className="space-y-1.5">
      {label && (
        <label className="block text-[12px] font-medium text-[hsl(var(--muted-foreground))] uppercase tracking-wider">
          {label}
        </label>
      )}
      <select
        className={cn(
          'w-full h-9 bg-[hsl(var(--secondary))] border border-[hsl(var(--border))] rounded-lg text-[13px] text-[hsl(var(--foreground))] px-3',
          'focus:outline-none focus:border-[hsl(var(--primary)/0.5)] focus:ring-1 focus:ring-[hsl(var(--primary)/0.2)]',
          'transition-all duration-150',
          className
        )}
        {...props}
      >
        {options.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}

// ─── Page Header ─────────────────────────────────────────
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h1 className="text-xl font-bold font-display text-[hsl(var(--foreground))] tracking-tight">
          {title}
        </h1>
        {description && (
          <p className="text-[13px] text-[hsl(var(--muted-foreground))] mt-0.5">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

// ─── Empty State ─────────────────────────────────────────
export function EmptyState({ icon, title, description, action }: {
  icon: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
      <div className="w-12 h-12 rounded-xl bg-[hsl(var(--accent))] flex items-center justify-center text-[hsl(var(--muted-foreground))]">
        {icon}
      </div>
      <div>
        <p className="text-[14px] font-medium text-[hsl(var(--foreground))]">{title}</p>
        {description && (
          <p className="text-[12px] text-[hsl(var(--muted-foreground))] mt-0.5">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

// ─── Toast ───────────────────────────────────────────────
export function useToast() {
  const [toasts, setToasts] = React.useState<{ id: number; message: string; type: 'success' | 'error' | 'info' }[]>([]);

  const toast = React.useCallback((message: string, type: 'success' | 'error' | 'info' = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3500);
  }, []);

  const ToastContainer = () => (
    <div className="fixed bottom-5 right-5 z-[9999] space-y-2">
      {toasts.map(t => (
        <div
          key={t.id}
          className={cn(
            'flex items-center gap-2.5 px-4 py-3 rounded-lg text-[13px] font-medium shadow-xl border animate-fade-in',
            t.type === 'success' && 'bg-[hsl(var(--card))] border-[hsl(var(--green)/0.3)] text-[hsl(var(--foreground))]',
            t.type === 'error' && 'bg-[hsl(var(--card))] border-[hsl(var(--red)/0.3)] text-[hsl(var(--foreground))]',
            t.type === 'info' && 'bg-[hsl(var(--card))] border-[hsl(var(--border))] text-[hsl(var(--foreground))]',
          )}
        >
          <span className={cn(
            'w-1.5 h-1.5 rounded-full flex-shrink-0',
            t.type === 'success' && 'bg-[hsl(var(--green))]',
            t.type === 'error' && 'bg-[hsl(var(--red))]',
            t.type === 'info' && 'bg-[hsl(var(--blue))]',
          )} />
          {t.message}
        </div>
      ))}
    </div>
  );

  return { toast, ToastContainer };
}

// ─── Loading Skeleton ────────────────────────────────────
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('shimmer rounded-lg', className)} />;
}

// ─── Modal ───────────────────────────────────────────────
export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-md bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-2xl shadow-2xl animate-fade-in">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[hsl(var(--border))]">
          <h3 className="text-[14px] font-semibold font-display text-[hsl(var(--foreground))]">
            {title}
          </h3>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--accent))] transition-colors text-lg leading-none"
          >
            ×
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

function useEffect(fn: () => (() => void) | void, deps: unknown[]) {
  React.useEffect(fn as () => void, deps);
}
