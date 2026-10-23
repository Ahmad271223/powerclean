/**
 * Small Apple-style UI kit for the Stundenzettel app:
 * pill buttons, cards, segmented control, inputs, toggle, chips, sheet (dialog) and the glass header.
 */
import React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { Loader2, X, ChevronDown } from 'lucide-react';
import { cn } from '../lib/utils';

export const ACCENT = '#C41E3A';

const btnVariants = {
  primary: 'bg-[#C41E3A] text-white hover:bg-[#AD1A33] shadow-[0_8px_20px_-8px_rgba(196,30,58,0.55)]',
  dark: 'bg-[#1D1D1F] text-white hover:bg-black',
  soft: 'bg-black/[0.05] text-[#1D1D1F] hover:bg-black/[0.09]',
  ghost: 'text-[#1D1D1F] hover:bg-black/[0.05]',
  danger: 'text-[#C41E3A] hover:bg-[#C41E3A]/10',
  white: 'bg-white text-[#1D1D1F] shadow-card hover:shadow-card-hover',
};
const btnSizes = { sm: 'h-9 px-3.5 text-[13px]', md: 'h-11 px-5 text-[15px]', lg: 'h-[52px] px-7 text-[16px]' };

export function Btn({ variant = 'primary', size = 'md', loading = false, className, children, ...props }) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-full font-semibold whitespace-nowrap select-none',
        'transition-all duration-150 active:scale-[0.97] disabled:opacity-50 disabled:pointer-events-none',
        btnVariants[variant], btnSizes[size], className,
      )}
      {...props}
    >
      {loading && <Loader2 size={18} className="animate-spin" />}
      {children}
    </button>
  );
}

export function IconBtn({ className, variant = 'ghost', size = 36, children, ...props }) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-full transition-all duration-150 active:scale-95 disabled:opacity-40 disabled:pointer-events-none',
        btnVariants[variant], className,
      )}
      style={{ width: size, height: size }}
      {...props}
    >
      {children}
    </button>
  );
}

export function Card({ className, children, ...props }) {
  return (
    <div className={cn('bg-white rounded-[22px] shadow-card', className)} {...props}>
      {children}
    </div>
  );
}

/** iOS style segmented control. options: [{value, label, icon?}] */
export function Segmented({ value, onChange, options, className }) {
  return (
    <div className={cn('inline-flex p-1 rounded-full bg-black/[0.06]', className)} role="tablist">
      {options.map((o) => {
        const Icon = o.icon;
        const active = o.value === value;
        return (
          <button
            key={o.value}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={cn(
              'flex items-center gap-2 px-4 h-9 rounded-full text-[14px] font-semibold transition-all duration-200',
              active ? 'bg-white text-[#1D1D1F] shadow-[0_1px_3px_rgba(0,0,0,0.12)]' : 'text-[#6E6E73] hover:text-[#1D1D1F]',
            )}
            data-testid={o.testId}
          >
            {Icon && <Icon size={16} />} {o.label}
          </button>
        );
      })}
    </div>
  );
}

export const inputClass =
  'w-full h-11 rounded-xl bg-[#F5F5F7] border border-transparent px-3.5 text-[15px] text-[#1D1D1F] placeholder:text-[#A1A1A6] ' +
  'outline-none transition-all focus:bg-white focus:border-[#C41E3A]/40 focus:ring-4 focus:ring-[#C41E3A]/10 disabled:opacity-50';

export const TextInput = React.forwardRef(({ className, ...props }, ref) => (
  <input ref={ref} className={cn(inputClass, className)} {...props} />
));
TextInput.displayName = 'TextInput';

export const TextArea = React.forwardRef(({ className, ...props }, ref) => (
  <textarea ref={ref} className={cn(inputClass, 'h-auto py-2.5 resize-none', className)} {...props} />
));
TextArea.displayName = 'TextArea';

/** Native select styled like a pill with chevron. */
export function Select({ className, children, ...props }) {
  return (
    <span className={cn('relative inline-flex', className)}>
      <select
        className="appearance-none h-10 pl-4 pr-9 rounded-full bg-black/[0.05] hover:bg-black/[0.09] text-[15px] font-semibold text-[#1D1D1F] outline-none focus:ring-4 focus:ring-[#C41E3A]/10 cursor-pointer"
        {...props}
      >
        {children}
      </select>
      <ChevronDown size={15} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[#6E6E73]" />
    </span>
  );
}

export function Field({ label, hint, className, children }) {
  return (
    <label className={cn('block', className)}>
      <span className="block text-[13px] font-medium text-[#6E6E73] mb-1.5">{label}</span>
      {children}
      {hint && <span className="block text-[12px] text-[#86868B] mt-1.5">{hint}</span>}
    </label>
  );
}

/** Section label inside forms / sheets. */
export function SectionLabel({ children, className }) {
  return <h3 className={cn('text-[12px] font-semibold uppercase tracking-[0.08em] text-[#86868B]', className)}>{children}</h3>;
}

/** iOS style switch. */
export function Toggle({ checked, onChange, label, hint, testId }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="w-full flex items-center justify-between gap-4 py-2 text-left"
      data-testid={testId}
    >
      <span>
        <span className="block text-[15px] text-[#1D1D1F]">{label}</span>
        {hint && <span className="block text-[12px] text-[#86868B]">{hint}</span>}
      </span>
      <span className={cn('relative shrink-0 w-[51px] h-[31px] rounded-full transition-colors duration-200', checked ? 'bg-[#34C759]' : 'bg-black/[0.12]')}>
        <span className={cn('absolute top-[2px] left-[2px] w-[27px] h-[27px] rounded-full bg-white shadow-[0_3px_8px_rgba(0,0,0,0.15)] transition-transform duration-200', checked && 'translate-x-5')} />
      </span>
    </button>
  );
}

/** Selectable pill chip. */
export function Chip({ active, className, children, ...props }) {
  return (
    <button
      type="button"
      className={cn(
        'h-9 px-3.5 rounded-full text-[13px] font-semibold transition-all duration-150 active:scale-95 whitespace-nowrap',
        active ? 'bg-[#1D1D1F] text-white' : 'bg-black/[0.05] text-[#1D1D1F] hover:bg-black/[0.09]',
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

/**
 * Sheet: modal dialog that slides up from the bottom on phones and is a centred rounded card on larger screens.
 */
export function Sheet({ open, onOpenChange, title, subtitle, width = 'sm:max-w-lg', children, footer }) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/35 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
        <DialogPrimitive.Content
          className={cn(
            'ts-app ts-sheet fixed z-50 left-1/2 -translate-x-1/2 bottom-0 sm:bottom-auto sm:top-1/2 sm:-translate-y-1/2',
            'w-full sm:w-[calc(100%-2rem)] flex flex-col outline-none',
            'bg-white rounded-t-[28px] sm:rounded-[28px] shadow-[0_30px_80px_-20px_rgba(0,0,0,0.35)]',
            'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0',
            'data-[state=open]:slide-in-from-bottom-6 data-[state=closed]:slide-out-to-bottom-6 sm:data-[state=open]:zoom-in-95 sm:data-[state=closed]:zoom-out-95',
            width,
          )}
        >
          <div className="sm:hidden mx-auto mt-2.5 w-10 h-1.5 rounded-full bg-black/15" />
          <div className="flex items-start justify-between gap-4 px-6 pt-5 pb-3">
            <div className="min-w-0">
              <DialogPrimitive.Title className="text-[22px] font-bold tracking-tight text-[#1D1D1F] leading-tight">{title}</DialogPrimitive.Title>
              <DialogPrimitive.Description className={cn('text-[14px] text-[#6E6E73] mt-1', !subtitle && 'sr-only')}>
                {subtitle || title}
              </DialogPrimitive.Description>
            </div>
            <DialogPrimitive.Close className="shrink-0 w-8 h-8 rounded-full bg-black/[0.06] hover:bg-black/[0.12] flex items-center justify-center transition-colors" aria-label="Schließen">
              <X size={16} />
            </DialogPrimitive.Close>
          </div>
          <div className="px-6 pb-6 overflow-y-auto overscroll-contain">{children}</div>
          {footer && <div className="px-6 py-4 border-t border-black/[0.06] bg-white rounded-b-[28px]">{footer}</div>}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/** Frosted-glass sticky header. */
export function AppHeader({ left, right, className }) {
  return (
    <header className={cn('sticky top-0 z-40 safe-top backdrop-blur-xl bg-[#F5F5F7]/80 border-b border-black/[0.06]', className)}>
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">{left}</div>
        <div className="flex items-center gap-1.5 sm:gap-2">{right}</div>
      </div>
    </header>
  );
}

export function PageHeading({ title, subtitle, action, className }) {
  return (
    <div className={cn('flex flex-wrap items-end justify-between gap-4', className)}>
      <div>
        <h1 className="text-[32px] sm:text-[40px] font-bold tracking-tight leading-none">{title}</h1>
        {subtitle && <p className="text-[15px] text-[#6E6E73] mt-2">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

/** App-icon like square with initials. */
export function AppIcon({ color = ACCENT, text, size = 56, className, logo }) {
  if (logo) {
    return (
      <span className={cn('inline-flex items-center justify-center rounded-2xl bg-white shadow-card overflow-hidden shrink-0', className)} style={{ width: size, height: size }}>
        <img src={logo} alt="" className="max-w-[86%] max-h-[86%] object-contain" />
      </span>
    );
  }
  return (
    <span
      className={cn('inline-flex items-center justify-center rounded-2xl text-white font-bold shrink-0', className)}
      style={{ width: size, height: size, backgroundImage: `linear-gradient(145deg, ${color} 0%, ${color}CC 100%)`, fontSize: size * 0.38 }}
    >
      {text}
    </span>
  );
}

export function Empty({ icon: Icon, title, text, action }) {
  return (
    <div className="flex flex-col items-center text-center py-16 px-6">
      {Icon && <span className="w-14 h-14 rounded-2xl bg-black/[0.05] flex items-center justify-center text-[#6E6E73] mb-4"><Icon size={26} /></span>}
      <h3 className="text-[17px] font-semibold">{title}</h3>
      {text && <p className="text-[14px] text-[#6E6E73] mt-1 max-w-sm">{text}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
