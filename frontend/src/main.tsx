import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
import { ApiError } from './api/client'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      refetchOnWindowFocus: false,
      // 4xx means the request was wrong; retrying it changes nothing.
      retry: (failureCount, error) => {
        if (error instanceof ApiError && error.status < 500) return false
        return failureCount < 2
      },
    },
  },
})

const container = document.getElementById('root')
if (!container) throw new Error('#root not found in index.html')

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
