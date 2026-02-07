/**
 * Frontend error handling utilities.
 *
 * Provides utilities to sanitize error messages, extract error information
 * from various response shapes, and retrieve error codes for support reference.
 *
 * This module implements STORY-005 of the holistic API error handling feature.
 */

/**
 * Fallback message when sanitization strips everything meaningful.
 */
export const FALLBACK_MESSAGE = 'An unexpected error occurred';

/**
 * SQL keywords to detect and remove from error messages.
 */
const SQL_KEYWORDS = [
  'SELECT',
  'INSERT',
  'UPDATE',
  'DELETE',
  'FROM',
  'WHERE',
  'JOIN',
  'LEFT JOIN',
  'RIGHT JOIN',
  'INNER JOIN',
  'OUTER JOIN',
  'CREATE',
  'DROP',
  'ALTER',
  'TRUNCATE',
  'VALUES',
  'SET',
  'INTO',
  'TABLE',
  'INDEX',
  'ON',
  'AND',
  'OR',
  'NOT NULL',
  'PRIMARY KEY',
  'FOREIGN KEY',
  'REFERENCES',
  'CONSTRAINT',
  'UNIQUE',
  'CASCADE',
  'DEFAULT',
  'NULL',
  'RETURNING',
  'ORDER BY',
  'GROUP BY',
  'HAVING',
  'LIMIT',
  'OFFSET',
  'UNION',
  'EXCEPT',
  'INTERSECT',
] as const;

/**
 * Known database table names in this application.
 * These are explicitly listed to catch them even without SQL context.
 */
const DB_TABLE_NAMES = [
  'users',
  'shootouts',
  'jobs',
  'tones',
  'di_tracks',
  'signal_chains',
  'signal_chain_blocks',
  'signal_chain_groups',
  'signal_chain_group_di',
  'signal_chain_group_amp',
  'signal_chain_group_ir',
  'signal_chain_group_signal_chains',
  't3k_packs',
  't3k_models',
  't3k_related',
  'user_gear',
  'tags',
  'audit_logs',
] as const;

/**
 * Patterns that indicate file paths.
 */
const FILE_PATH_PATTERNS = [
  /\/app\//gi,
  /\/home\//gi,
  /\/usr\//gi,
  /\/var\//gi,
  /\/tmp\//gi,
  /\/data\//gi,
  /\.py[c]?/gi,
  /\/backend\//gi,
  /\/frontend\//gi,
  /guitar-tone-shootout/gi,
];

/**
 * Regex patterns for sensitive content.
 */
const SENSITIVE_PATTERNS = [
  // SQL statements (case insensitive)
  /\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b.*?(?:;|$)/gi,
  // Table.column references (any column name with underscore)
  /\b\w+\.\w+_\w+\b/gi,
  // Table.column references (just _id suffix)
  /\b\w+\.\w+_id\b/gi,
  // Column names in quotes
  /"[\w_]+"/gi,
  // Python traceback headers
  /Traceback \(most recent call last\):.*?(?:\n\n|$)/gis,
  // File paths with line numbers
  /File "[^"]+", line \d+/gi,
  // Generic file paths
  /(?:\/[\w.-]+)+\.py[c]?(?::\d+)?/gi,
  // Stack frame references
  /in \w+\n\s+\w+.*/gim,
  // SQL constraint names
  /\b\w+_pkey\b|\b\w+_fkey\b|\b\w+_key\b|\b\w+_idx\b/gi,
];

/**
 * Remove sensitive content from a message string.
 *
 * @param message - The message to sanitize.
 * @returns The sanitized message.
 */
function removeSensitiveContent(message: string): string {
  let result = message;

  // Remove content matching sensitive patterns
  for (const pattern of SENSITIVE_PATTERNS) {
    // Reset lastIndex for global patterns
    pattern.lastIndex = 0;
    result = result.replace(pattern, '');
  }

  // Remove SQL keywords (case insensitive)
  for (const keyword of SQL_KEYWORDS) {
    // Match as whole word
    const pattern = new RegExp(`\\b${escapeRegExp(keyword)}\\b`, 'gi');
    result = result.replace(pattern, '');
  }

  // Remove known table names
  for (const table of DB_TABLE_NAMES) {
    // Match table name as whole word or with common suffixes
    const pattern = new RegExp(`\\b${escapeRegExp(table)}(?:_\\w+)?\\b`, 'gi');
    result = result.replace(pattern, '');
  }

  // Remove file path patterns
  for (const pathPattern of FILE_PATH_PATTERNS) {
    // Reset lastIndex for global patterns
    pathPattern.lastIndex = 0;
    result = result.replace(pathPattern, '');
  }

  // Remove PostgreSQL-specific patterns
  result = result.replace(/\brelation\b/gi, '');
  result = result.replace(/\bviolates\b/gi, '');
  result = result.replace(/\bconstraint\b/gi, '');
  result = result.replace(/\bcolumn\b/gi, '');

  // Clean up whitespace
  result = result.replace(/\s+/g, ' ');
  result = result.trim();

  // Remove dangling punctuation
  result = result.replace(/^[:\s,.-]+|[:\s,.-]+$/g, '');
  result = result.replace(/\s+[:\s,.-]+\s+/g, ' ');

  return result.trim();
}

/**
 * Escape special regex characters in a string.
 *
 * @param str - The string to escape.
 * @returns The escaped string.
 */
function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Sanitize an error message by removing sensitive information.
 *
 * Removes SQL queries, database table/column names, file paths,
 * and stack traces from error messages before they are displayed to users.
 *
 * @param error - The error to sanitize (string or Error object).
 * @returns A sanitized, user-friendly error message.
 *
 * @example
 * ```ts
 * sanitizeErrorMessage('SELECT * FROM users WHERE id = 123');
 * // Returns: 'An unexpected error occurred'
 *
 * sanitizeErrorMessage(new Error('Invalid email format'));
 * // Returns: 'Invalid email format'
 * ```
 */
export function sanitizeErrorMessage(error: Error | string): string {
  // Extract the message string
  const message = error instanceof Error ? error.message : error;

  // Handle empty messages
  if (!message || typeof message !== 'string' || !message.trim()) {
    return FALLBACK_MESSAGE;
  }

  // Apply sanitization
  const sanitized = removeSensitiveContent(message);

  // If sanitization removed everything, return fallback
  if (!sanitized || !sanitized.trim()) {
    return FALLBACK_MESSAGE;
  }

  return sanitized;
}

/**
 * Type guard to check if a value is an object with string properties.
 */
function isErrorObject(
  error: unknown
): error is Record<string, unknown> & { [key: string]: unknown } {
  return typeof error === 'object' && error !== null;
}

/**
 * Extract error message from various error shapes and sanitize it.
 *
 * Handles multiple error response formats:
 * - `{ detail: string }` - Common API error format
 * - `{ error: { message: string, code?: string } }` - Nested error format
 * - `{ message: string }` - Simple object with message
 * - `{ code: string, message: string }` - Flat API error format
 * - Plain strings
 * - Error objects
 *
 * @param error - The error to extract a message from.
 * @returns A sanitized, user-friendly error message.
 *
 * @example
 * ```ts
 * getErrorMessage({ detail: 'Not found' });
 * // Returns: 'Not found'
 *
 * getErrorMessage({ error: { message: 'Auth required', code: 'AUTH_001' } });
 * // Returns: 'Auth required'
 *
 * getErrorMessage(new Error('Something went wrong'));
 * // Returns: 'Something went wrong'
 * ```
 */
export function getErrorMessage(error: unknown): string {
  // Handle null/undefined
  if (error === null || error === undefined) {
    return FALLBACK_MESSAGE;
  }

  // Handle strings directly
  if (typeof error === 'string') {
    return sanitizeErrorMessage(error);
  }

  // Handle Error objects
  if (error instanceof Error) {
    return sanitizeErrorMessage(error);
  }

  // Handle object shapes
  if (isErrorObject(error)) {
    // Priority 1: Nested error.message (for { error: { message } } shape)
    if (
      isErrorObject(error.error) &&
      typeof error.error.message === 'string' &&
      error.error.message.trim()
    ) {
      return sanitizeErrorMessage(error.error.message);
    }

    // Priority 2: Direct message property (for { message } shape)
    if (typeof error.message === 'string' && error.message.trim()) {
      return sanitizeErrorMessage(error.message);
    }

    // Priority 3: detail property (for { detail } shape)
    if (typeof error.detail === 'string' && error.detail.trim()) {
      return sanitizeErrorMessage(error.detail);
    }
  }

  // Fallback for unhandled types
  return FALLBACK_MESSAGE;
}

/**
 * Valid error code pattern: CATEGORY_NNN
 * Categories: AUTH, PERM, VAL, NOT_FOUND, CONFLICT, RATE, EXT, INT
 */
const ERROR_CODE_PATTERN = /^[A-Z]+(?:_[A-Z]+)*_\d{3}$/;

/**
 * Extract the error code from an error response.
 *
 * Validates that the code follows the CATEGORY_NNN format
 * (e.g., AUTH_001, VAL_002, NOT_FOUND_001).
 *
 * @param error - The error to extract the code from.
 * @returns The error code, or null if not found or invalid format.
 *
 * @example
 * ```ts
 * extractErrorCode({ error: { code: 'AUTH_001', message: 'Test' } });
 * // Returns: 'AUTH_001'
 *
 * extractErrorCode({ code: 'VAL_002' });
 * // Returns: 'VAL_002'
 *
 * extractErrorCode({ message: 'No code here' });
 * // Returns: null
 * ```
 */
export function extractErrorCode(error: unknown): string | null {
  // Handle null/undefined/non-objects
  if (!isErrorObject(error)) {
    return null;
  }

  let code: unknown = null;

  // Check nested error.code first (for { error: { code } } shape)
  if (isErrorObject(error.error) && error.error.code !== undefined) {
    code = error.error.code;
  }
  // Check direct code property (for flat { code } shape)
  else if (error.code !== undefined) {
    code = error.code;
  }

  // Validate code is a non-empty string
  if (typeof code !== 'string' || !code.trim()) {
    return null;
  }

  // Normalize to uppercase
  const normalizedCode = code.toUpperCase();

  // Validate format matches CATEGORY_NNN pattern
  if (!ERROR_CODE_PATTERN.test(normalizedCode)) {
    return null;
  }

  return normalizedCode;
}
