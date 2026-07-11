/**
 * UI Component Library - Executive Talent Engine Design System
 * 
 * Re-export all components for easy imports:
 * import { Button, Card, Input } from '@/components/ui';
 */

export { Badge, StatusBadge, StatusDot } from './Badge';
export { Button } from './Button';
export { Card, CardHeader, CardTitle, CardContent, CardFooter } from './Card';
export { Input, Textarea, Select } from './Input';
export { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from './Table';

// Re-export existing components
export { Skeleton, CandidateSkeleton, JobSkeleton, TableSkeleton } from '../Skeleton';
export { EmptyState, NoCandidatesEmpty, NoJobsEmpty, NoResultsEmpty, ErrorEmpty } from '../EmptyState';
export { ErrorBoundary } from '../ErrorBoundary';
