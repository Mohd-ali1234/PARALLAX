import type { UseQueryResult } from '@tanstack/react-query'

import { SOURCE_TYPE_LABELS, type Document, type Page } from '../api/types'

interface Props {
  query: UseQueryResult<Page<Document>>
}

function formatPeriod(doc: Document): string {
  if (doc.fiscal_year && doc.fiscal_quarter) return `FY${doc.fiscal_year} Q${doc.fiscal_quarter}`
  if (doc.fiscal_year) return `FY${doc.fiscal_year}`
  return '—'
}

export function DocumentTable({ query }: Props) {
  const { data, error, isPending } = query

  if (isPending) return <p className="muted">Loading documents…</p>

  if (error) {
    return (
      <p className="error" role="alert">
        Could not load documents: {error.message}
      </p>
    )
  }

  if (data.items.length === 0) {
    return <p className="muted">No documents registered yet.</p>
  }

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">Title</th>
            <th scope="col">Source</th>
            <th scope="col">Period</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((doc) => (
            <tr key={doc.id}>
              <td className="table__title">{doc.title}</td>
              <td>{SOURCE_TYPE_LABELS[doc.source_type]}</td>
              <td>{formatPeriod(doc)}</td>
              <td>
                <span className={`badge badge--${doc.status}`}>{doc.status}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">
        Showing {data.items.length} of {data.total}
      </p>
    </div>
  )
}
