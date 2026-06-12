import { cn } from '@/lib/utils'
import { ButtonHTMLAttributes, forwardRef } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'outline' | 'secondary' | 'ghost' | 'destructive' | 'link'
  size?: 'default' | 'sm' | 'lg' | 'icon' | 'xs'
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', ...props }, ref) => {
    const base = 'inline-flex items-center justify-center rounded-lg font-medium text-sm transition-all disabled:pointer-events-none disabled:opacity-50 whitespace-nowrap'

    const variants: Record<string, string> = {
      default:     'bg-primary text-primary-foreground hover:bg-primary/90',
      outline:     'border border-border bg-background hover:bg-muted',
      secondary:   'bg-secondary text-secondary-foreground hover:bg-secondary/80',
      ghost:       'hover:bg-muted hover:text-foreground',
      destructive: 'bg-destructive/10 text-destructive hover:bg-destructive/20',
      link:        'text-primary underline-offset-4 hover:underline',
    }

    const sizes: Record<string, string> = {
      default: 'h-8 px-3 gap-1.5',
      xs:      'h-6 px-2 text-xs gap-1',
      sm:      'h-7 px-2.5 text-xs gap-1',
      lg:      'h-10 px-4 gap-2',
      icon:    'h-8 w-8',
    }

    return (
      <button
        ref={ref}
        className={cn(base, variants[variant], sizes[size], className)}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'

export { Button }
