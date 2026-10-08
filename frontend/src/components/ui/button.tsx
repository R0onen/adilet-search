import type { ButtonHTMLAttributes } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

// shadcn-style local primitive: Radix handles dialogs; this button uses native semantics.
export function Button({ className, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={twMerge(clsx('button', className))} {...props} />;
}
