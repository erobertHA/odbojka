const API = '/api'

export async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${url}`, options)
  if (!res.ok) {
    let detail = 'Prišlo je do napake.'
    let siteLocked = false
    try {
      const body = await res.json()
      if (body.locked) {
        siteLocked = true
        window.dispatchEvent(new Event('site-locked'))
      }
      detail = typeof body.detail === 'string' ? body.detail : detail
    } catch {}
    if (res.status === 401 && url.startsWith('/admin/') && !siteLocked) {
      detail = 'Administratorska seja je potekla ali ni več veljavna. Prijavi se znova.'
      window.dispatchEvent(new CustomEvent('admin-unauthorized', {
        detail: new Headers(options?.headers).get('Authorization'),
      }))
    }
    throw new Error(detail)
  }
  return res.json()
}

