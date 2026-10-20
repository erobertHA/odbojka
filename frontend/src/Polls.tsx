import { useEffect, useState, type FormEvent } from 'react'
import { api } from './api'

type Question = { text: string; options: string[]; multiple?: boolean }
type Poll = { id: number; title: string; questions: Question[]; active: boolean; created_at: string; archived_at: string | null }
type Results = Poll & { total: number; counts: number[][] }
type AdminPoll = Results & { submissions: { id: number; name: string; answers: (number | number[])[]; created_at: string }[] }

const tokenKey = (id: number) => `volleyball_poll_${id}`
function savedToken(id: number) {
  try { return sessionStorage.getItem(tokenKey(id)) } catch { return null }
}
function date(value: string) {
  return new Intl.DateTimeFormat('sl-SI', {dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Ljubljana'}).format(new Date(value))
}
function errorMessage(error: unknown) { return error instanceof Error ? error.message : 'Prišlo je do napake.' }

function PollResults({results}: {results: Results}) {
  return <div className="poll-results" aria-live="polite">
    <p><strong>Rezultati</strong> · Oddanih odgovorov: {results.total}</p>
    {results.questions.map((question, qi) => <div key={qi}>
      <h3>{question.text}</h3>
      {question.multiple && <p className="muted">Možnih je več odgovorov.</p>}
      {question.options.map((option, oi) => {
        const count = results.counts[qi][oi]
        const percent = results.total ? Math.round(count / results.total * 100) : 0
        return <div className="poll-result" key={oi}>
          <div><span>{option}</span><strong>{count} od {results.total} · {percent} %</strong></div>
          <div className="poll-bar" aria-hidden="true"><span style={{width: `${percent}%`}} /></div>
        </div>
      })}
    </div>)}
  </div>
}

function PollCard({poll, onArchived}: {poll: Poll; onArchived: () => void}) {
  const [name, setName] = useState('')
  const [answers, setAnswers] = useState<Record<number, number[]>>({})
  const [token, setToken] = useState(() => savedToken(poll.id))
  const [results, setResults] = useState<Results | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function refreshResults() {
    if (!token) return
    setBusy(true)
    setError('')
    try { setResults(await api<Results>(`/polls/${poll.id}/results`, {headers: {'X-Poll-Token': token}})) }
    catch (error) { setError(errorMessage(error)); onArchived() }
    finally { setBusy(false) }
  }
  useEffect(() => { if (token) void refreshResults() }, [token])

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!name.trim()) { setError('Vpiši svoje ime.'); return }
    if (poll.questions.some((_, index) => !answers[index]?.length)) { setError('Odgovori na vsako vprašanje.'); return }
    setBusy(true); setError('')
    try {
      const result = await api<{token: string; results: Results}>(`/polls/${poll.id}/vote`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, answers: poll.questions.map((question, index) => question.multiple ? answers[index] : answers[index][0])}),
      })
      try { sessionStorage.setItem(tokenKey(poll.id), result.token) } catch {}
      setResults(result.results); setToken(result.token)
    } catch (error) {
      setError(errorMessage(error))
      onArchived()
    } finally { setBusy(false) }
  }

  return <section className="card poll-card" aria-labelledby={`poll-title-${poll.id}`}>
    <div className="eyebrow">ANKETA ZA NAŠO SKUPINO</div>
    <h2 id={`poll-title-${poll.id}`}>{poll.title}</h2>
    {results ? <><p role="status">Hvala za tvoj odgovor!</p><PollResults results={results} /><button className="secondary" disabled={busy} onClick={refreshResults}>Osveži rezultate</button></>
      : token ? <><p>Tvoj odgovor je že oddan.</p><button className="secondary" disabled={busy} onClick={refreshResults}>Prikaži rezultate</button></>
      : <form className="form" onSubmit={submit}>
        <p className="poll-intro">Odgovori na vsa vprašanja. Rezultate vidiš po oddaji.</p>
        <label>Tvoje ime za anketo<input value={name} onChange={e => setName(e.target.value)} required maxLength={80} placeholder="Ime ali vzdevek" /></label>
        {poll.questions.map((question, qi) => <fieldset className="poll-question" key={qi}>
          <legend>{question.text}</legend>
          <p className="poll-hint">{question.multiple ? 'Izberi enega ali več odgovorov.' : 'Izberi en odgovor.'}</p>
          {question.options.map((option, oi) => <label className="poll-option" key={oi}>
            <input type={question.multiple ? 'checkbox' : 'radio'} name={`poll-${poll.id}-${qi}`} value={oi} checked={(answers[qi] || []).includes(oi)} onChange={e => {
              const selected = answers[qi] || []
              setAnswers({...answers, [qi]: question.multiple
                ? e.target.checked ? [...selected, oi] : selected.filter(value => value !== oi)
                : [oi]})
            }} required={!question.multiple} />
            <span>{option}</span>
          </label>)}
        </fieldset>)}
        <p className="muted">Organizator vidi tvoje ime in odgovore. Vsako ime lahko odgovori enkrat na anketo.</p>
        <button className="primary" disabled={busy}>{busy ? 'Pošiljam…' : 'Oddaj odgovore in prikaži rezultate'}</button>
      </form>}
    {error && <p className="message error" role="alert">{error}</p>}
  </section>
}

export function PublicPolls() {
  const [polls, setPolls] = useState<Poll[]>([])
  const [error, setError] = useState('')
  async function load() {
    try { setPolls(await api<Poll[]>('/polls/active')); setError('') }
    catch (error) { setError(errorMessage(error)) }
  }
  useEffect(() => {
    void load()
    const timer = window.setInterval(load, 60000)
    const focus = () => { void load() }
    window.addEventListener('focus', focus)
    return () => { window.clearInterval(timer); window.removeEventListener('focus', focus) }
  }, [])
  if (!polls.length && !error) return null
  return <div className="shell polls-shell">
    {error && <p className="message error" role="alert">Anket ni mogoče osvežiti. {error} <button className="secondary" onClick={load}>Poskusi znova</button></p>}
    {polls.map(poll => <PollCard key={poll.id} poll={poll} onArchived={load} />)}
  </div>
}

const blankQuestion = (): Question => ({text: '', options: ['', ''], multiple: false})
export function AdminPolls({token}: {token: string}) {
  const [polls, setPolls] = useState<AdminPoll[]>([])
  const [title, setTitle] = useState('')
  const [questions, setQuestions] = useState<Question[]>([blankQuestion()])
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [loaded, setLoaded] = useState(false)
  async function request<T>(path: string, options: RequestInit = {}) {
    return api<T>(path, {...options, headers: {'Content-Type': 'application/json', Authorization: `Bearer ${token}`}})
  }
  async function load() { setPolls(await request<AdminPoll[]>('/admin/polls')); setLoaded(true) }
  useEffect(() => { load().catch(error => setError(errorMessage(error))) }, [token])
  function updateQuestion(index: number, question: Question) { setQuestions(questions.map((current, i) => i === index ? question : current)) }
  async function create(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(''); setMessage('')
    try {
      await request('/admin/polls', {method: 'POST', body: JSON.stringify({title, questions})})
      setTitle(''); setQuestions([blankQuestion()]); setMessage('Anketa je objavljena.'); await load()
    } catch (error) { setError(errorMessage(error)) }
    finally { setBusy(false) }
  }
  async function archive(poll: AdminPoll) {
    if (!window.confirm(`Arhiviram anketo »${poll.title}«? Uporabnikom ne bo več vidna.`)) return
    setBusy(true); setError(''); setMessage('')
    try { await request(`/admin/polls/${poll.id}/archive`, {method: 'POST'}); setMessage('Anketa je arhivirana.'); await load() }
    catch (error) { setError(errorMessage(error)) }
    finally { setBusy(false) }
  }
  function summary(poll: AdminPoll) {
    return <>
      <p className="muted">Dodano: {date(poll.created_at)}{poll.archived_at && ` · Arhivirano: ${date(poll.archived_at)}`}</p>
      <PollResults results={poll} />
      <h4>Kdo je odgovarjal</h4>
      {poll.submissions.length ? <div className="people-list">{poll.submissions.map(vote => <div className="person" key={vote.id}>
        <strong>{vote.name}</strong><span>{date(vote.created_at)}</span>
        <ul>{poll.questions.map((question, index) => <li key={index}>{question.text}: <strong>{(Array.isArray(vote.answers[index]) ? vote.answers[index] as number[] : [vote.answers[index] as number]).map(option => question.options[option]).join(', ')}</strong></li>)}</ul>
      </div>)}</div> : <p className="muted">Odgovorov še ni.</p>}
    </>
  }
  return <section className="card admin-polls" aria-labelledby="admin-polls-title">
    <div className="section-title"><h2 id="admin-polls-title">Ankete</h2><button className="secondary" disabled={busy} onClick={() => load().catch(error => setError(errorMessage(error)))}>Osveži</button></div>
    <p>Objavi eno ali več vprašanj. Vsako vprašanje ima od 2 do 20 ponujenih odgovorov.</p>
    <form className="form" onSubmit={create}>
      <label>Naslov ankete<input value={title} onChange={e => setTitle(e.target.value)} maxLength={200} required /></label>
      {questions.map((question, qi) => <fieldset className="poll-question poll-editor" key={qi}>
        <legend>Vprašanje {qi + 1}</legend>
        <label className="poll-option poll-mode"><input type="checkbox" checked={!!question.multiple} onChange={e => updateQuestion(qi, {...question, multiple: e.target.checked})} /><span>Dovoli več odgovorov pri tem vprašanju</span></label>
        <label>Besedilo vprašanja<input value={question.text} onChange={e => updateQuestion(qi, {...question, text: e.target.value})} maxLength={500} required /></label>
        {question.options.map((option, oi) => <label key={oi}>Odgovor {oi + 1}<input value={option} onChange={e => updateQuestion(qi, {...question, options: question.options.map((value, i) => i === oi ? e.target.value : value)})} maxLength={200} required /></label>)}
        <div className="poll-actions">
          <button className="secondary" type="button" disabled={question.options.length >= 20} onClick={() => updateQuestion(qi, {...question, options: [...question.options, '']})}>Dodaj odgovor</button>
          <button className="secondary" type="button" disabled={question.options.length <= 2} onClick={() => updateQuestion(qi, {...question, options: question.options.slice(0, -1)})}>Odstrani zadnji odgovor</button>
          {questions.length > 1 && <button className="danger" type="button" onClick={() => setQuestions(questions.filter((_, i) => i !== qi))}>Odstrani vprašanje</button>}
        </div>
      </fieldset>)}
      <button className="secondary" type="button" disabled={questions.length >= 20} onClick={() => setQuestions([...questions, blankQuestion()])}>Dodaj vprašanje</button>
      <button className="primary" disabled={busy}>{busy ? 'Shranjujem…' : 'Objavi anketo'}</button>
    </form>
    {error && <p className="message error" role="alert">{error}</p>}
    {message && <p role="status">{message}</p>}
    <h3>Aktivne ankete</h3>
    {!loaded && !error && <p>Nalagam ankete…</p>}
    {loaded && !polls.some(poll => poll.active) && <p className="muted">Ni aktivnih anket.</p>}
    {polls.filter(poll => poll.active).map(poll => <div className="edit-panel" key={poll.id}>
      <h3>{poll.title}</h3>{summary(poll)}<button className="secondary" disabled={busy} onClick={() => archive(poll)}>Arhiviraj anketo</button>
    </div>)}
    <h3>Arhiv anket</h3>
    {loaded && !polls.some(poll => !poll.active) && <p className="muted">Arhiv anket je prazen.</p>}
    {polls.filter(poll => !poll.active).map(poll => <details className="edit-panel" key={poll.id}>
      <summary>{poll.title} · {date(poll.created_at)} · {poll.total} odgovorov</summary>{summary(poll)}
    </details>)}
  </section>
}
