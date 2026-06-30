import createClient, { type Middleware } from 'openapi-fetch'
import type { paths } from './schema'

type ApiErrorResponse = {
  detail?: unknown
  message?: unknown
  code?: unknown
  request_id?: unknown
  error?: {
    message?: unknown
    code?: unknown
  }
}

const FALLBACK_MESSAGE = 'An unexpected error occurred'
const ERROR_CODE_PATTERN = /^[A-Z]+_\d{3}$/

export class ApiError extends Error {
  readonly code: string | null
  readonly requestId: string | null
  readonly originalResponse: unknown

  constructor(
    message: string,
    code: string | null = null,
    requestId: string | null = null,
    originalResponse: unknown = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.requestId = requestId
    this.originalResponse = originalResponse
  }
}

function isErrorResponse(value: unknown): value is ApiErrorResponse {
  return typeof value === 'object' && value !== null
}

function asNonEmptyString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null
}

function getErrorMessage(errorData: unknown): string {
  if (!isErrorResponse(errorData)) return FALLBACK_MESSAGE

  const nestedMessage = isErrorResponse(errorData.error)
    ? asNonEmptyString(errorData.error.message)
    : null
  return (
    nestedMessage
    ?? asNonEmptyString(errorData.detail)
    ?? asNonEmptyString(errorData.message)
    ?? FALLBACK_MESSAGE
  )
}

function extractErrorCode(errorData: unknown): string | null {
  if (!isErrorResponse(errorData)) return null

  const nestedCode = isErrorResponse(errorData.error)
    ? asNonEmptyString(errorData.error.code)
    : null
  const code = nestedCode ?? asNonEmptyString(errorData.code)
  return code && ERROR_CODE_PATTERN.test(code) ? code : null
}

function extractRequestId(errorData: unknown): string | null {
  if (!isErrorResponse(errorData)) return null
  return asNonEmptyString(errorData.request_id)
}

async function parseErrorResponse(response: Response): Promise<unknown> {
  return response
    .clone()
    .json()
    .catch(() => ({
      detail: `HTTP ${response.status}: ${response.statusText}`,
    }))
}

const errorMiddleware: Middleware = {
  async onResponse({ response }) {
    if (response.ok) return response

    const errorData = await parseErrorResponse(response)
    throw new ApiError(
      getErrorMessage(errorData),
      extractErrorCode(errorData),
      extractRequestId(errorData),
      errorData,
    )
  },
}

export const apiClient = createClient<paths>({
  credentials: 'include',
})

apiClient.use(errorMiddleware)
