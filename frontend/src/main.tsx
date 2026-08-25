import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

type RSVPStatus = 'playing' | 'drinks' | 'no'

type ResponseItem = {
  id: number
  name: string
  response: RSVPStatus
  note?: string | null
  client_token?: string
}

type EventItem = {
  id: number
  date: string
  start_time: string
  end_time?: string | null
  location: string
  description?: string | null
  minimum_players: number
  signup_deadline?: string | null
  active: boolean
  responses: ResponseItem[]
}

const API = '/api'

const labels: Record<RSVPStatus, string> = {
  playing: 'Igram',
  drinks: 'Samo na pijačo',
  no: 'Ne pridem',
}

function slDate(value: string) {
  const d = new Date(`${value}T12:00:00`)
  return new Intl.DateTimeFormat('sl-SI', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(d)
}

async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${url}`, options)
  if (!res.ok) {
    let detail = 'Prišlo je do napake.'
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {}
    throw new Error(detail)
  }
  return res.json()
}

function PublicPage() {
  const [event, setEvent] = useState<EventItem | null | undefined>(undefined)
  const [name, setName] = useState(localStorage.getItem('volleyball_name') || '')
  const [status, setStatus] = useState<RSVPStatus>('playing')
  const [note, setNote] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  async function load() {
    setEvent(await api<EventItem | null>('/events/current'))
  }

  useEffect(() => { load() }, [])

  useEffect(() => {
    if (!event) return
    const saved = localStorage.getItem(`volleyball_rsvp_${event.id}`)
    if (!saved) return
    try {
      const mine = JSON.parse(saved)
      if (mine.name) setName(mine.name)
      if (mine.response) setStatus(mine.response)
      setNote(mine.note || '')
    } catch {}
  }, [event])

  const groups = useMemo(() => {
    const source = event?.responses || []
    return {
      playing: source.filter(r => r.response === 'playing'),
      drinks: source.filter(r => r.response === 'drinks'),
      no: source.filter(r => r.response === 'no'),
    }
  }, [event])

  if (event === undefined) return <main className="shell"><div className="card">Nalagam…</div></main>

  if (!event) {
    return (
      <main className="shell narrow">
        <section className="hero">
          <div className="eyebrow">ODBOJKA</div>
          <h1>Trenutno ni odprtega termina.</h1>
          <p>Ko admin objavi naslednji termin, se bo prikazal tukaj.</p>
        </section>
      </main>
    )
  }

  const currentEvent = event

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setBusy(true)
    setMessage('')
    try {
      const key = `volleyball_token_${currentEvent.id}`
      const client_token = localStorage.getItem(key)
      const result = await api<{client_token: string}>(`/events/${currentEvent.id}/rsvp`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name, response: status, note, client_token }),
      })
      localStorage.setItem(key, result.client_token)
      localStorage.setItem('volleyball_name', name)
      localStorage.setItem(`volleyball_rsvp_${currentEvent.id}`, JSON.stringify({name, response: status, note}))
      setMessage('Odgovor je shranjen.')
      await load()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Napaka.')
    } finally {
      setBusy(false)
    }
  }

  const count = groups.playing.length
  const missing = Math.max(event.minimum_players - count, 0)

  return (
    <main className="shell">
      <section className="hero">
        <div className="eyebrow">NASLEDNJI TERMIN</div>
        <h1>{slDate(event.date)}</h1>
        <div className="event-meta">
          <span>{event.start_time}{event.end_time ? `–${event.end_time}` : ''}</span>
          <span>•</span>
          <span>{event.location}</span>
        </div>
        {event.description && <p>{event.description}</p>}
      </section>

      <section className="score card">
        <div>
          <strong>{count}</strong>
          <span>igralcev</span>
        </div>
        <div className="progress-wrap">
          <div className="progress"><div style={{width: `${Math.min((count / event.minimum_players) * 100, 100)}%`}} /></div>
          <small>{missing ? `Manjka še ${missing} do minimuma ${event.minimum_players}.` : `Dovolj igralcev za termin.`}</small>
        </div>
      </section>

      <section className="card">
        <h2>Tvoj odgovor</h2>
        <form onSubmit={submit} className="form">
          <label>
            Ime
            <input value={name} onChange={e => setName(e.target.value)} maxLength={80} required placeholder="Tvoje ime" />
          </label>

          <div className="choices">
            {(['playing', 'drinks', 'no'] as RSVPStatus[]).map(value => (
              <button type="button" key={value} className={`choice ${status === value ? 'active' : ''}`} onClick={() => setStatus(value)}>
                <span>{value === 'playing' ? '🏐' : value === 'drinks' ? '🍺' : '✕'}</span>
                {labels[value]}
              </button>
            ))}
          </div>

          <label>
            Opomba <span className="muted">(neobvezno)</span>
            <input value={note} onChange={e => setNote(e.target.value)} maxLength={300} placeholder="npr. pridem 15 min kasneje" />
          </label>

          <button className="primary" disabled={busy}>{busy ? 'Shranjujem…' : 'Shrani odgovor'}</button>
          {message && <div className="message">{message}</div>}
        </form>
      </section>

      {event.signup_deadline && <div className="deadline">Prijave do: {event.signup_deadline.replace('T', ' ')}</div>}

      <PeopleGroup title="Igrajo" items={groups.playing} />
      <PeopleGroup title="Samo na pijačo" items={groups.drinks} />
      <PeopleGroup title="Ne pridejo" items={groups.no} />

      <footer><a href="/admin">Admin</a></footer>
    </main>
  )
}

function PeopleGroup({title, items}: {title: string, items: ResponseItem[]}) {
  return (
    <section className="card people">
      <div className="section-title"><h2>{title}</h2><span>{items.length}</span></div>
      {items.length === 0 ? <p className="muted">Zaenkrat nihče.</p> : (
        <div className="people-list">
          {items.map(item => (
            <div className="person" key={item.id}>
              <strong>{item.name}</strong>
              {item.note && <span>{item.note}</span>}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function AdminPage() {
  const [token, setToken] = useState(sessionStorage.getItem('admin_token') || '')
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [events, setEvents] = useState<EventItem[]>([])
  const [error, setError] = useState('')
  const [form, setForm] = useState({
    date: '',
    start_time: '19:30',
    end_time: '21:00',
    location: '',
    description: '',
    minimum_players: 6,
    signup_deadline: '',
  })

  async function adminApi<T>(url: string, options: RequestInit = {}): Promise<T> {
    return api<T>(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...(options.headers || {}),
      },
    })
  }

  async function load() {
    if (!token) return
    try {
      setEvents(await adminApi<EventItem[]>('/admin/events'))
      setError('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Napaka.')
    }
  }

  useEffect(() => { load() }, [token])

  async function login(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    try {
      const result = await api<{token: string}>('/auth/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username, password}),
      })
      sessionStorage.setItem('admin_token', result.token)
      setToken(result.token)
      setPassword('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Napaka.')
    }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault()
    try {
      await adminApi('/admin/events', {method: 'POST', body: JSON.stringify({...form, signup_deadline: form.signup_deadline || null})})
      setForm({...form, date: '', location: '', description: '', signup_deadline: ''})
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Napaka.')
    }
  }

  async function closeEvent(id: number) {
    await adminApi(`/admin/events/${id}/close`, {method: 'POST'})
    await load()
  }

  async function deleteResponse(id: number) {
    if (!confirm('Odstranim to prijavo?')) return
    await adminApi(`/admin/responses/${id}`, {method: 'DELETE'})
    await load()
  }

  if (!token) {
    return (
      <main className="shell narrow">
        <section className="hero"><div className="eyebrow">ADMIN</div><h1>Prijava</h1></section>
        <section className="card">
          <form onSubmit={login} className="form">
            <label>Uporabniško ime<input value={username} onChange={e => setUsername(e.target.value)} /></label>
            <label>Geslo<input type="password" value={password} onChange={e => setPassword(e.target.value)} /></label>
            <button className="primary">Prijava</button>
            {error && <div className="message error">{error}</div>}
          </form>
        </section>
      </main>
    )
  }

  const active = events.find(e => e.active)

  return (
    <main className="shell">
      <section className="hero admin-header">
        <div><div className="eyebrow">ADMIN</div><h1>Upravljanje terminov</h1></div>
        <button className="secondary" onClick={() => {sessionStorage.removeItem('admin_token'); setToken('')}}>Odjava</button>
      </section>

      {error && <div className="message error">{error}</div>}

      <section className="card">
        <h2>Nov termin</h2>
        <p className="muted">Objava novega termina samodejno zapre trenutno aktivnega.</p>
        <form onSubmit={create} className="form grid">
          <label>Datum<input type="date" value={form.date} onChange={e => setForm({...form, date: e.target.value})} required /></label>
          <label>Začetek<input type="time" value={form.start_time} onChange={e => setForm({...form, start_time: e.target.value})} required /></label>
          <label>Konec<input type="time" value={form.end_time} onChange={e => setForm({...form, end_time: e.target.value})} /></label>
          <label>Minimum igralcev<input type="number" min="1" max="50" value={form.minimum_players} onChange={e => setForm({...form, minimum_players: Number(e.target.value)})} /></label>
          <label className="wide">Lokacija<input value={form.location} onChange={e => setForm({...form, location: e.target.value})} required placeholder="npr. Dvorana Vič" /></label>
          <label className="wide">Opis<input value={form.description} onChange={e => setForm({...form, description: e.target.value})} placeholder="neobvezno" /></label>
          <label className="wide">Rok prijave<input type="datetime-local" value={form.signup_deadline} onChange={e => setForm({...form, signup_deadline: e.target.value})} /></label>
          <button className="primary wide">Objavi termin</button>
        </form>
      </section>

      {active && (
        <section className="card">
          <div className="section-title"><h2>Aktivni termin</h2><span>{active.responses.filter(r => r.response === 'playing').length} igralcev</span></div>
          <p><strong>{slDate(active.date)}</strong> · {active.start_time} · {active.location}</p>
          <div className="admin-responses">
            {active.responses.map(r => (
              <div className="admin-response" key={r.id}>
                <div><strong>{r.name}</strong><span>{labels[r.response]}{r.note ? ` · ${r.note}` : ''}</span></div>
                <button className="danger" onClick={() => deleteResponse(r.id)}>Izbriši</button>
              </div>
            ))}
          </div>
          <button className="secondary" onClick={() => closeEvent(active.id)}>Zaključi termin</button>
        </section>
      )}

      <section className="card">
        <h2>Arhiv</h2>
        <div className="people-list">
          {events.filter(e => !e.active).map(e => (
            <div className="person" key={e.id}>
              <strong>{slDate(e.date)} · {e.start_time}</strong>
              <span>{e.location} · {e.responses.filter(r => r.response === 'playing').length} igralcev</span>
            </div>
          ))}
          {events.filter(e => !e.active).length === 0 && <p className="muted">Arhiv je še prazen.</p>}
        </div>
      </section>

      <footer><a href="/">Nazaj na javno stran</a></footer>
    </main>
  )
}

function App() {
  return window.location.pathname.startsWith('/admin') ? <AdminPage /> : <PublicPage />
}

createRoot(document.getElementById('root')!).render(
  <React.StrictMode><App /></React.StrictMode>
)
