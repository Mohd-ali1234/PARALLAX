import { useState } from 'react'

import { DocumentTable } from './components/DocumentTable'
import { ServiceStatus } from './components/ServiceStatus'
import { useDocuments } from './api/queries'
import { SOURCE_TYPE_LABELS, type SourceType } from './api/types'

const SOURCE_TYPES = Object.keys(SOURCE_TYPE_LABELS) as SourceType[]

export default function App() {
  const [sourceType, setSourceType] = useState<SourceType | undefined>(undefined)
  const documents = useDocuments(sourceType ? { source_type: sourceType } : {})

  return (
    <div className="app">
      <header className="app__header">
        <div>
          <h1 className="app__title">PARALLAX</h1>
          <p className="app__subtitle">Multimodal Financial Verification Engine</p>
        </div>
        <ServiceStatus />
      </header>

      <main className="app__main">
        <section className="panel">
          <div className="panel__head">
            <h2 className="panel__title">Ingested documents</h2>
            <div className="filters" role="group" aria-label="Filter by source type">
              <button
                type="button"
                className={`chip${sourceType === undefined ? ' chip--active' : ''}`}
                onClick={() => setSourceType(undefined)}
                aria-pressed={sourceType === undefined}
              >
                All
              </button>
              {SOURCE_TYPES.map((type) => (
                <button
                  key={type}
                  type="button"
                  className={`chip${sourceType === type ? ' chip--active' : ''}`}
                  onClick={() => setSourceType(type)}
                  aria-pressed={sourceType === type}
                >
                  {SOURCE_TYPE_LABELS[type]}
                </button>
              ))}
            </div>
          </div>

          <DocumentTable query={documents} />
        </section>

        <p className="note">
          Ingestion, the agent lanes, and the reconciliation engine are not built yet. This view
          reads the document registry so the API, database, and browser are provably connected.
        </p>
      </main>
    </div>
  )
}
