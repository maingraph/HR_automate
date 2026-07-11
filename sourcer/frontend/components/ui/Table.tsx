/**
 * Table component - Executive Talent Engine Design System
 * 
 * High-density data tables with horizontal dividers only.
 * "Agentic" look for quick scanning of recruitment data.
 */

import { HTMLAttributes, ThHTMLAttributes, TdHTMLAttributes } from 'react';

interface TableProps extends HTMLAttributes<HTMLTableElement> {}

export function Table({ className = '', children, ...props }: TableProps) {
  return (
    <div className="w-full overflow-x-auto">
      <table className={`w-full ${className}`} {...props}>
        {children}
      </table>
    </div>
  );
}

/**
 * Table Header
 */
export function TableHeader({ className = '', children, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead className={`border-b border-outline-variant ${className}`} {...props}>
      {children}
    </thead>
  );
}

/**
 * Table Body
 */
export function TableBody({ className = '', children, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody className={className} {...props}>
      {children}
    </tbody>
  );
}

/**
 * Table Row
 */
export function TableRow({ className = '', children, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr className={`border-b border-outline-variant hover:bg-surface-container-low transition-colors ${className}`} {...props}>
      {children}
    </tr>
  );
}

/**
 * Table Head Cell
 */
export function TableHead({ className = '', children, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th className={`text-left px-4 py-3 font-label text-label-caps text-on-surface-variant uppercase ${className}`} {...props}>
      {children}
    </th>
  );
}

/**
 * Table Cell
 */
export function TableCell({ className = '', children, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={`px-4 py-3 font-body text-body-sm text-on-surface ${className}`} {...props}>
      {children}
    </td>
  );
}
