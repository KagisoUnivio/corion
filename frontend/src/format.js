export function southAfricanToday() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Africa/Johannesburg',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts().filter(({ type }) => type !== 'literal')
    .map(({ value }) => value).join('-');
}

export function displayDate(iso) {
  return iso.split('-').reverse().join('/');
}

export function parseDate(value) {
  if (!/^\d{2}\/\d{2}\/\d{4}$/.test(value)) return null;
  const iso = value.split('/').reverse().join('-');
  const date = new Date(iso + 'T00:00:00Z');
  return !iso.startsWith('0000') && !Number.isNaN(date.getTime())
    && date.toISOString().slice(0, 10) === iso ? iso : null;
}

export function positiveDecimal(value) {
  return /^(?:\d+(?:\.\d*)?|\.\d+)$/.test(value) && /[1-9]/.test(value);
}

export function money(value, currency) {
  // Round the server's decimal string without losing precision to binary floats.
  const [whole, fraction = ''] = String(value).split('.');
  const cents = BigInt(whole) * 100n + BigInt((fraction + '00').slice(0, 2))
    + (Number(fraction[2]) >= 5 ? 1n : 0n);
  const units = (cents / 100n).toLocaleString('en-GB');
  return currency + ' ' + units + '.' + String(cents % 100n).padStart(2, '0');
}
