# Phase 2 Frontend Refactoring — Detailed Plan

**Status:** 📋 PLANNING (Read-Only Mode)  
**Date:** 2026-04-27  
**Planner:** OpenCode (kr/claude-sonnet-4.5)  
**Estimated Duration:** 1-2 weeks  
**Complexity:** Medium

---

## 🎯 Objectives

Based on Phase 1 analysis and identified style conflicts between Claude Opus and Gemini 3.1 in the frontend:

1. **Eliminate component duplication** — Field component duplicated in `outreach/new/page.tsx`
2. **Create reusable form management hooks** — Standardize form state management
3. **Standardize async patterns** — Unify async/await vs `.then().catch()` chains
4. **Improve TypeScript type safety** — Add proper types, eliminate `any`
5. **Unify useEffect dependency patterns** — Fix infinite loop risks

---

## 📊 Current State Analysis

### Frontend Codebase Metrics
- **Total Lines:** 3,887 lines
- **TSX Files:** 10 pages
- **Components:** 1 shared file (`ui.tsx`, 223 lines)
- **API Client:** 1 file (`api.ts`, 119 lines)

### Identified Issues

#### 1. Component Duplication (CRITICAL)
**Location:** `frontend/app/outreach/new/page.tsx:71-78`

```typescript
// DUPLICATED - also exists in ui.tsx
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="grid gap-1">
      <span className="text-xs uppercase tracking-wide text-[var(--muted)]">{label}</span>
      {children}
    </label>
  );
}
```

**vs ui.tsx:145-161:**
```typescript
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="grid gap-1.5">
      <span className="text-xs font-medium uppercase tracking-wider text-[var(--muted)]">{label}</span>
      {children}
      {hint && <span className="text-xs text-[var(--muted)] opacity-70">{hint}</span>}
    </label>
  );
}
```

**Problem:** Two versions with different features (hint support, styling differences)

#### 2. Async Pattern Inconsistency (HIGH)
**Found 32 instances of `.then().catch()` chains**

**Pattern A (Claude style):** async/await with try/catch
```typescript
// app/page.tsx:77-122
const onSubmit = async () => {
  setLoading(true);
  try {
    const job = await apiFetch<{ id: string }>("/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    router.push(`/jobs/${job.id}`);
  } catch (err) {
    setError((err as Error).message);
  } finally {
    setLoading(false);
  }
};
```

**Pattern B (Gemini style):** Promise chains
```typescript
// app/admin/credentials/page.tsx:44-50
apiFetch<Creds>("/admin/credentials").then((data) => {
  setCreds(data);
  setLiMinDelay(String(data.li_send_min_delay ?? 30));
  // ...
}).catch(() => {}).finally(() => setLoading(false));
```

**Pattern C (Mixed):** async/await with inline .catch()
```typescript
// app/outreach/page.tsx:22
const data = await getCampaigns().catch(() => []);
```

#### 3. Form State Management (HIGH)
**Multiple patterns identified:**

**Pattern A:** Single state object (Wizard pattern)
```typescript
// app/page.tsx:42-53
const [form, setForm] = useState({
  title: "",
  description: "",
  skills: "",
  // ... 10+ fields
});
```

**Pattern B:** Individual state per field
```typescript
// app/outreach/new/page.tsx:86-92
const [name, setName] = useState("FB Media Buyer — CIS");
const [jobId, setJobId] = useState("");
const [tgTemplate, setTgTemplate] = useState(DEFAULT_TG_TEMPLATE);
const [liTemplate, setLiTemplate] = useState(DEFAULT_LI_TEMPLATE);
// ... 8+ individual states
```

**Problem:** No consistent pattern, difficult to validate, lots of boilerplate

#### 4. useEffect Dependency Issues (MEDIUM)
**17 useEffect instances found**

**Correct pattern (fixed in Phase 1 docs):**
```typescript
// app/outreach/page.tsx:45-49
useEffect(() => {
  load();
  const iv = setInterval(load, 10000);
  return () => clearInterval(iv);
}, [load]); // ✓ Stable ref only
```

**Potential issue pattern:**
```typescript
// Need to verify all 17 instances don't have array lengths or object properties
}, [load, campaigns.length]); // ✗ BAD - causes infinite loops
```

#### 5. Type Safety Issues (MEDIUM)
**Examples:**
- Inline type definitions instead of shared types
- Missing return types on functions
- `any` types in some places
- Inconsistent type imports

---

## 🗺️ Detailed Refactoring Plan

### Task 1: Eliminate Component Duplication (2-3 hours)

#### 1.1 Audit All Components
**Action:** Search for duplicated components across all pages

**Files to check:**
- `app/outreach/new/page.tsx` — Field component (confirmed)
- All other pages — check for other duplications

**Deliverable:** List of all duplicated components

#### 1.2 Consolidate Field Component
**Action:** Remove local Field from `outreach/new/page.tsx`, use ui.tsx version

**Changes:**
```typescript
// app/outreach/new/page.tsx
// REMOVE lines 71-78 (local Field component)

// ADD import at top:
import { Field } from "@/components/ui";

// UPDATE all Field usages to support hint prop if needed
```

**Testing:** Verify form still renders correctly

#### 1.3 Enhance ui.tsx Field Component
**Action:** Ensure Field component supports all use cases

**Add features:**
- Error message display
- Required field indicator
- Disabled state
- Custom className support

**New signature:**
```typescript
export function Field({
  label,
  hint,
  error,
  required,
  children,
  className,
}: {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`grid gap-1.5 ${className || ""}`}>
      <span className="text-xs font-medium uppercase tracking-wider text-[var(--muted)]">
        {label}
        {required && <span className="text-red-400 ml-1">*</span>}
      </span>
      {children}
      {error && <span className="text-xs text-red-400">{error}</span>}
      {hint && <span className="text-xs text-[var(--muted)] opacity-70">{hint}</span>}
    </label>
  );
}
```

---

### Task 2: Create Reusable Form Hooks (4-6 hours)

#### 2.1 Create useForm Hook
**Action:** Create `frontend/lib/hooks/useForm.ts`

**Features:**
- Generic type support
- Validation rules
- Error handling
- Touched state tracking
- Reset functionality
- Submit handling

**Implementation:**
```typescript
// frontend/lib/hooks/useForm.ts
import { useState, useCallback } from 'react';

type ValidationRule<T> = {
  field: keyof T;
  validate: (value: any, formData: T) => string | null;
};

type UseFormOptions<T> = {
  initialValues: T;
  validations?: ValidationRule<T>[];
  onSubmit: (values: T) => Promise<void> | void;
};

export function useForm<T extends Record<string, any>>({
  initialValues,
  validations = [],
  onSubmit,
}: UseFormOptions<T>) {
  const [values, setValues] = useState<T>(initialValues);
  const [errors, setErrors] = useState<Partial<Record<keyof T, string>>>({});
  const [touched, setTouched] = useState<Partial<Record<keyof T, boolean>>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const setValue = useCallback(<K extends keyof T>(field: K, value: T[K]) => {
    setValues(prev => ({ ...prev, [field]: value }));
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
  }, [errors]);

  const setFieldTouched = useCallback(<K extends keyof T>(field: K) => {
    setTouched(prev => ({ ...prev, [field]: true }));
  }, []);

  const validate = useCallback((): boolean => {
    const newErrors: Partial<Record<keyof T, string>> = {};
    
    for (const rule of validations) {
      const error = rule.validate(values[rule.field], values);
      if (error) {
        newErrors[rule.field] = error;
      }
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [values, validations]);

  const handleSubmit = useCallback(async (e?: React.FormEvent) => {
    e?.preventDefault();
    
    // Mark all fields as touched
    const allTouched = Object.keys(values).reduce((acc, key) => {
      acc[key as keyof T] = true;
      return acc;
    }, {} as Partial<Record<keyof T, boolean>>);
    setTouched(allTouched);
    
    if (!validate()) {
      return;
    }
    
    setIsSubmitting(true);
    try {
      await onSubmit(values);
    } finally {
      setIsSubmitting(false);
    }
  }, [values, validate, onSubmit]);

  const reset = useCallback(() => {
    setValues(initialValues);
    setErrors({});
    setTouched({});
    setIsSubmitting(false);
  }, [initialValues]);

  return {
    values,
    errors,
    touched,
    isSubmitting,
    setValue,
    setFieldTouched,
    handleSubmit,
    reset,
    setValues,
  };
}
```

#### 2.2 Create useAsync Hook
**Action:** Create `frontend/lib/hooks/useAsync.ts`

**Purpose:** Standardize async operations with loading/error states

**Implementation:**
```typescript
// frontend/lib/hooks/useAsync.ts
import { useState, useCallback } from 'react';

type UseAsyncOptions<T> = {
  onSuccess?: (data: T) => void;
  onError?: (error: Error) => void;
};

export function useAsync<T, Args extends any[]>(
  asyncFunction: (...args: Args) => Promise<T>,
  options: UseAsyncOptions<T> = {}
) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<T | null>(null);

  const execute = useCallback(async (...args: Args) => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await asyncFunction(...args);
      setData(result);
      options.onSuccess?.(result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      options.onError?.(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [asyncFunction, options]);

  const reset = useCallback(() => {
    setLoading(false);
    setError(null);
    setData(null);
  }, []);

  return {
    loading,
    error,
    data,
    execute,
    reset,
  };
}
```

#### 2.3 Refactor Forms to Use Hooks
**Action:** Update all forms to use new hooks

**Priority order:**
1. `app/page.tsx` — Wizard form (most complex)
2. `app/outreach/new/page.tsx` — Campaign creation
3. Other forms as needed

**Example refactoring:**
```typescript
// BEFORE (app/outreach/new/page.tsx:80-122)
const [name, setName] = useState("FB Media Buyer — CIS");
const [jobId, setJobId] = useState("");
// ... 8+ individual states

const onSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  setLoading(true);
  try {
    const campaign = await apiFetch(/* ... */);
    router.push(`/outreach/${campaign.id}`);
  } catch (err) {
    setError((err as Error).message);
  } finally {
    setLoading(false);
  }
};

// AFTER
const { values, errors, isSubmitting, setValue, handleSubmit } = useForm({
  initialValues: {
    name: "FB Media Buyer — CIS",
    jobId: "",
    tgTemplate: DEFAULT_TG_TEMPLATE,
    // ...
  },
  validations: [
    {
      field: 'name',
      validate: (v) => !v.trim() ? 'Campaign name is required' : null,
    },
  ],
  onSubmit: async (values) => {
    const campaign = await apiFetch(/* ... */);
    router.push(`/outreach/${campaign.id}`);
  },
});
```

---

### Task 3: Standardize Async Patterns (3-4 hours)

#### 3.1 Define Standard Pattern
**Decision:** Use async/await with try/catch as standard

**Rationale:**
- More readable
- Better error handling
- Consistent with backend refactoring
- Easier to debug

**Standard pattern:**
```typescript
// ✓ GOOD
const handleAction = async () => {
  setLoading(true);
  setError(null);
  
  try {
    const result = await apiCall();
    // Handle success
  } catch (err) {
    setError(err instanceof Error ? err.message : 'Unknown error');
  } finally {
    setLoading(false);
  }
};

// ✗ AVOID
apiCall().then(result => {
  // Handle success
}).catch(err => {
  setError(err.message);
}).finally(() => {
  setLoading(false);
});
```

#### 3.2 Refactor All Async Calls
**Action:** Update all 32 instances of `.then().catch()`

**Files to update:**
- `app/outreach/page.tsx` (3 instances)
- `app/admin/logs/page.tsx` (2 instances)
- `app/outreach/[id]/page.tsx` (11 instances)
- `app/outreach/new/page.tsx` (1 instance)
- `app/admin/credentials/page.tsx` (4 instances)
- `app/outreach/review/page.tsx` (3 instances)
- `app/outreach/inbox/page.tsx` (5 instances)
- `app/jobs/[id]/page.tsx` (3 instances)

**Special case:** Inline `.catch(() => [])` for fallback values

**Solution:** Use useAsync hook or helper function
```typescript
// BEFORE
const data = await getCampaigns().catch(() => []);

// AFTER (Option 1: helper function)
const data = await getCampaigns().catch(() => [] as Campaign[]);

// AFTER (Option 2: useAsync hook)
const { data, loading, execute } = useAsync(getCampaigns, {
  onError: () => {}, // Silent fail with empty array
});
```

---

### Task 4: Improve TypeScript Type Safety (2-3 hours)

#### 4.1 Create Shared Types File
**Action:** Create `frontend/lib/types.ts`

**Move types from:**
- Inline definitions in pages
- api.ts (keep API-specific types there)

**Structure:**
```typescript
// frontend/lib/types.ts

// Form types
export type VacancyFormData = {
  title: string;
  description: string;
  skills: string;
  geo: string;
  geo_exclude: string;
  seniority: string;
  budget_min: string | number;
  budget_max: string | number;
  tg_channels: string;
  sources: string[];
};

export type CampaignFormData = {
  name: string;
  jobId: string;
  tgTemplate: string;
  liTemplate: string;
  questions: string[];
  tgAccount: string;
  qualificationNote: string;
};

// Component prop types
export type FieldProps = {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
};

// ... more shared types
```

#### 4.2 Add Function Return Types
**Action:** Add explicit return types to all functions

**Example:**
```typescript
// BEFORE
const load = useCallback(async () => {
  const data = await getCampaigns().catch(() => []);
  setCampaigns(data);
  setLoading(false);
}, []);

// AFTER
const load = useCallback(async (): Promise<void> => {
  const data = await getCampaigns().catch(() => [] as Campaign[]);
  setCampaigns(data);
  setLoading(false);
}, []);
```

#### 4.3 Eliminate `any` Types
**Action:** Search for `any` and replace with proper types

**Command:** `grep -r "any" frontend/app frontend/lib`

**Replace with:**
- Specific types
- Generic types
- `unknown` (if truly unknown, then narrow with type guards)

---

### Task 5: Unify useEffect Patterns (2-3 hours)

#### 5.1 Audit All useEffect Calls
**Action:** Review all 17 useEffect instances

**Check for:**
- Array lengths in dependencies (causes infinite loops)
- Object properties in dependencies
- Missing cleanup functions
- Unnecessary dependencies

**Files to audit:**
- `app/outreach/page.tsx` (1 instance)
- `app/admin/logs/page.tsx` (1 instance)
- `app/outreach/[id]/page.tsx` (1 instance)
- `app/outreach/new/page.tsx` (1 instance)
- `app/admin/credentials/page.tsx` (1 instance)
- `app/outreach/review/page.tsx` (1 instance)
- `app/outreach/inbox/page.tsx` (2 instances)
- `app/jobs/[id]/page.tsx` (1 instance)

#### 5.2 Fix Problematic Patterns
**Action:** Update any problematic useEffect calls

**Pattern to fix:**
```typescript
// ✗ BAD
useEffect(() => {
  load();
}, [load, campaigns.length]); // campaigns.length causes re-render loop

// ✓ GOOD
useEffect(() => {
  load();
}, [load]); // Only stable ref
```

#### 5.3 Create useInterval Hook
**Action:** Create `frontend/lib/hooks/useInterval.ts`

**Purpose:** Standardize polling patterns

**Implementation:**
```typescript
// frontend/lib/hooks/useInterval.ts
import { useEffect, useRef } from 'react';

export function useInterval(callback: () => void, delay: number | null) {
  const savedCallback = useRef(callback);

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    if (delay === null) return;

    const id = setInterval(() => savedCallback.current(), delay);
    return () => clearInterval(id);
  }, [delay]);
}
```

**Usage:**
```typescript
// BEFORE
useEffect(() => {
  load();
  const iv = setInterval(load, 10000);
  return () => clearInterval(iv);
}, [load]);

// AFTER
useEffect(() => {
  load();
}, [load]);

useInterval(load, 10000);
```

---

## 📋 Implementation Checklist

### Phase 2.1: Component Consolidation (Day 1-2)
- [ ] Audit all components for duplication
- [ ] Remove local Field from `outreach/new/page.tsx`
- [ ] Enhance ui.tsx Field component
- [ ] Test all forms still render correctly
- [ ] Update imports across all pages

### Phase 2.2: Form Hooks (Day 3-5)
- [ ] Create `lib/hooks/useForm.ts`
- [ ] Create `lib/hooks/useAsync.ts`
- [ ] Create `lib/types.ts` for shared types
- [ ] Refactor `app/page.tsx` to use useForm
- [ ] Refactor `app/outreach/new/page.tsx` to use useForm
- [ ] Test form validation and submission

### Phase 2.3: Async Standardization (Day 6-7)
- [ ] Define standard async pattern
- [ ] Refactor all `.then().catch()` to async/await
- [ ] Update all 32 instances across 8 files
- [ ] Test error handling works correctly
- [ ] Verify loading states work

### Phase 2.4: Type Safety (Day 8)
- [ ] Move inline types to `lib/types.ts`
- [ ] Add return types to all functions
- [ ] Eliminate `any` types
- [ ] Run TypeScript compiler to verify
- [ ] Fix any type errors

### Phase 2.5: useEffect Cleanup (Day 9)
- [ ] Audit all 17 useEffect instances
- [ ] Fix any problematic dependency arrays
- [ ] Create `lib/hooks/useInterval.ts`
- [ ] Refactor polling patterns to use useInterval
- [ ] Test no infinite loops occur

### Phase 2.6: Testing & Documentation (Day 10)
- [ ] Manual testing of all pages
- [ ] Verify no regressions
- [ ] Update REFACTORING_CHANGELOG.md
- [ ] Update ARCHITECTURE.md with frontend patterns
- [ ] Create Phase 2 summary document

---

## 🧪 Testing Strategy

### Manual Testing Checklist
- [ ] Vacancy creation wizard (all 3 steps)
- [ ] Campaign creation form
- [ ] Campaign list page (polling works)
- [ ] Campaign detail page
- [ ] Inbox page
- [ ] Review queue page
- [ ] Admin credentials page
- [ ] Admin logs page
- [ ] Job detail page

### Regression Testing
- [ ] All forms submit correctly
- [ ] Validation errors display
- [ ] Loading states show
- [ ] Error messages display
- [ ] Polling/intervals work
- [ ] Navigation works
- [ ] No console errors
- [ ] No infinite loops

### Performance Testing
- [ ] Page load times unchanged
- [ ] No memory leaks from intervals
- [ ] Re-renders minimized

---

## 📊 Expected Metrics

### Code Quality Improvements
| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Component duplication | 1 | 0 | -100% |
| Async patterns | 3 | 1 | -67% |
| Form boilerplate | High | Low | -70% |
| Type safety | 80% | 95% | +15% |
| useEffect issues | Unknown | 0 | -100% |

### Lines of Code
| File | Before | After | Change |
|------|--------|-------|--------|
| Total frontend | 3,887 | ~3,600 | -7% |
| New hooks | 0 | ~300 | +300 |
| Refactored pages | 3,664 | ~3,300 | -10% |

---

## 🚨 Risks & Mitigation

### Risk 1: Breaking Changes
**Probability:** Medium  
**Impact:** High  
**Mitigation:**
- Thorough manual testing
- Test each page after refactoring
- Keep git commits small and focused
- Easy rollback if issues found

### Risk 2: Type Errors
**Probability:** Medium  
**Impact:** Medium  
**Mitigation:**
- Run TypeScript compiler frequently
- Fix type errors incrementally
- Use `unknown` instead of `any` when unsure

### Risk 3: Infinite Loops
**Probability:** Low  
**Impact:** High  
**Mitigation:**
- Careful review of useEffect dependencies
- Test polling behavior thoroughly
- Use useInterval hook for consistency

### Risk 4: Performance Regression
**Probability:** Low  
**Impact:** Medium  
**Mitigation:**
- Profile before/after
- Monitor re-render counts
- Use React DevTools Profiler

---

## 🎯 Success Criteria

Phase 2 will be considered successful when:

1. ✅ Zero component duplication
2. ✅ All forms use useForm hook
3. ✅ All async calls use async/await pattern
4. ✅ TypeScript compiler shows no errors
5. ✅ All useEffect calls follow best practices
6. ✅ All manual tests pass
7. ✅ No performance regressions
8. ✅ Documentation updated

---

## 📅 Timeline

**Total Estimated Time:** 10 days (2 weeks)

**Week 1:**
- Days 1-2: Component consolidation
- Days 3-5: Form hooks implementation

**Week 2:**
- Days 6-7: Async standardization
- Day 8: Type safety improvements
- Day 9: useEffect cleanup
- Day 10: Testing & documentation

---

## 🔄 Next Steps After Phase 2

**Phase 3: Performance Optimization**
- WebSocket/SSE for real-time updates
- Database views for aggregations
- Redis caching layer
- Batch processing optimization

**Phase 4: Production Hardening**
- Authentication system
- Monitoring and alerting
- Comprehensive test suite
- CI/CD pipeline

---

## 📞 Questions for User

Before starting implementation, please confirm:

1. **Priority:** Should we focus on all tasks or prioritize specific ones?
2. **Timeline:** Is 2 weeks acceptable or do we need faster delivery?
3. **Breaking changes:** Are you okay with potential minor breaking changes during refactoring?
4. **Testing:** Do you have a staging environment for testing?
5. **Deployment:** Can we deploy incrementally or need all-at-once?

---

**Plan Prepared By:** OpenCode (kr/claude-sonnet-4.5)  
**Date:** 2026-04-27T10:54:24Z  
**Status:** 📋 AWAITING APPROVAL  
**Next Step:** User review and approval to proceed

