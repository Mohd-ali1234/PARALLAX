import { ApiError } from '../api/client'
import { useReadiness } from '../api/queries'

/** Surfaces /health/ready, including the per-dependency checks it reports. */
export function ServiceStatus() {
  const { data, error, isPending } = useReadiness()

  if (isPending) {
    return (
      <div className="status status--pending">
        <span className="status__dot" aria-hidden="true" />
        Checking API…
      </div>
    )
  }

  if (error) {
    // 503 from the readiness probe means the API is up but Postgres is not.
    const unreachable = !(error instanceof ApiError)
    return (
      <div className="status status--down" role="status">
        <span className="status__dot" aria-hidden="true" />
        {unreachable ? 'API unreachable' : `Not ready — ${error.message}`}
      </div>
    )
  }

  return (
    <div className="status status--ok" role="status">
      <span className="status__dot" aria-hidden="true" />
      API ready
      <span className="status__meta">
        v{data.version} ·{' '}
        {Object.entries(data.checks)
          .map(([k, v]) => `${k}: ${v}`)
          .join(' · ')}
      </span>
    </div>
  )
}
