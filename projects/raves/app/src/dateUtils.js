/**
 * Parse a YYYY-MM-DD date string as LOCAL noon to avoid UTC offset shifting the day.
 * e.g. new Date('2026-06-27') → Jun 26 in ET (UTC-4)
 *      parseDate('2026-06-27') → Jun 27 always
 */
export function parseDate(dateStr) {
  if (!dateStr) return new Date()
  return new Date(dateStr + 'T12:00:00')
}

/** Today's date at local noon */
export function today() {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12, 0, 0)
}

/** YYYY-MM-DD string for today */
export function todayStr() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}
