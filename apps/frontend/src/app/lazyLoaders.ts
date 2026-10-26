/** Loaders for every component the app renders with `lazy()`. Components are lazy-loaded
 * only through this registry, so the test setup can preload all of them (P-3). */
export const lazyLoaders = {
  // Recharts is large; load it only with the profile page's chart.
  LanguageChart: () =>
    import('@/features/profile/LanguageChart').then((m) => ({ default: m.LanguageChart })),
}

export function preloadLazyComponents(): Promise<unknown> {
  return Promise.all(Object.values(lazyLoaders).map((load) => load()))
}
