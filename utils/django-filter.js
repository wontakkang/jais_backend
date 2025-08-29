// new file: utils/django-filter.js
export function buildDjangoFilterParams(params = {}) {
  const sp = new URLSearchParams();
  if (!params || typeof params !== 'object') return sp;
  for (const key of Object.keys(params)) {
    const val = params[key];
    if (val == null) continue;
    // if key already contains lookup (eg. field__gte)
    if (key.includes('__')) {
      if (Array.isArray(val)) {
        for (const v of val) sp.append(key, String(v));
      } else {
        sp.append(key, String(val));
      }
      continue;
    }
    // nested object -> flatten to key__sub
    if (typeof val === 'object' && !Array.isArray(val)) {
      for (const subKey of Object.keys(val)) {
        const subVal = val[subKey];
        if (subVal == null) continue;
        sp.append(`${key}__${subKey}`, String(subVal));
      }
      continue;
    }
    // arrays -> repeat same key for each value
    if (Array.isArray(val)) {
      for (const v of val) sp.append(key, String(v));
      continue;
    }
    sp.append(key, String(val));
  }
  return sp;
}
