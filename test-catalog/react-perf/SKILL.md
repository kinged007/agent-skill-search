---
name: react-perf
description: "Optimize React application performance: memo usage, virtualization, bundle splitting, lazy loading, and profiling with React DevTools."
metadata:
  hermes:
    category: frontend
---

# React Performance Optimization

## When to Use
When asked to speed up a React app, reduce bundle size, fix slow renders, or profile component re-renders.

## Procedure
1. Run `npx react-profiler` or use React DevTools Profiler
2. Identify components re-rendering unnecessarily
3. Apply `React.memo()`, `useMemo()`, `useCallback()` where beneficial
4. Implement code splitting with `React.lazy()` and `Suspense`
5. Add virtualization for long lists (react-window or react-virtuoso)

## Pitfalls
- Don't memo everything — profile first, optimize what matters
- useCallback without memo can actually be slower
