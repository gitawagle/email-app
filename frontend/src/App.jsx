import { useEffect, useMemo, useState } from 'react'
import './App.css'

const API_BASE = 'http://localhost:8000'

function initials(text) {
  return (text || '?').replace(/@.*/, '').slice(0, 2).toUpperCase()
}

function timeOfDayGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Morning'
  if (hour < 18) return 'Afternoon'
  return 'Evening'
}

function Avatar({ label }) {
  return <div className="avatar">{initials(label)}</div>
}

function Sidebar({ categories, activeCategory, onSelect, onAddCategory }) {
  const [adding, setAdding] = useState(false)
  const [newCategory, setNewCategory] = useState('')

  function submitNewCategory(e) {
    e.preventDefault()
    const name = newCategory.trim()
    if (!name) return
    onAddCategory(name)
    setNewCategory('')
    setAdding(false)
  }

  return (
    <aside className="sidebar">
      <div className="profile">
        <div className="profile-logo">✉</div>
        <div>
          <div className="profile-name">Email Tracker</div>
          <div className="muted">Personal inbox</div>
        </div>
      </div>

      {adding ? (
        <form onSubmit={submitNewCategory}>
          <input
            autoFocus
            className="search"
            placeholder="New category"
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value)}
            onBlur={() => !newCategory && setAdding(false)}
          />
        </form>
      ) : (
        <button type="button" className="nav-add" onClick={() => setAdding(true)}>
          + Add Category
        </button>
      )}

      <nav className="nav">
        {categories.map((c) => (
          <button
            key={c.name}
            type="button"
            title={c.description}
            className={`nav-item${c.name === activeCategory ? ' nav-active' : ''}`}
            onClick={() => onSelect(c.name)}
          >
            <span className="nav-label">{c.name}</span>
            {c.email_count > 0 && <span className="count">{c.email_count}</span>}
          </button>
        ))}
      </nav>
    </aside>
  )
}

function RefreshButton({ onRefreshed }) {
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState(null)

  async function handleClick() {
    setLoading(true)
    setMessage(null)
    try {
      const res = await fetch(`${API_BASE}/refresh`, { method: 'POST' })
      const body = await res.json()
      if (!res.ok) throw new Error(body.detail)
      const { total_new, analysis } = body
      const analyzed = analysis?.analyzed ? `, ${analysis.analyzed} analyzed` : ''
      setMessage(total_new === 0 ? `Up to date${analyzed}` : `${total_new} new${analyzed}`)
      onRefreshed()
    } catch (err) {
      console.error(err)
      setMessage('Refresh failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="refresh">
      {message && <span className="muted">{message}</span>}
      <button type="button" className="refresh-btn" onClick={handleClick} disabled={loading}>
        {loading ? 'Refreshing…' : '↻ Refresh'}
      </button>
    </div>
  )
}

const LABEL_CLASS = {
  'action needed': 'badge-danger',
  update: 'badge-info',
  promo: 'badge-muted',
}

function EmailList({ emails, sendersByAddress, query, onQuery, onRefreshed, showPromos, onTogglePromos, category }) {
  const today = new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })

  const q = query.toLowerCase()
  const visible = emails.filter((e) => (e.subject || '').toLowerCase().includes(q))

  return (
    <main className="main">
      <header className="main-header">
        <div className="greeting-block">
          <div className="eyebrow">{category}</div>
          <h1 className="greeting">Good {timeOfDayGreeting()}</h1>
          <p className="muted greeting-sub">{today}</p>
        </div>
        <div className="header-actions">
          <input
            className="search search-inline"
            placeholder="Search emails"
            value={query}
            onChange={(e) => onQuery(e.target.value)}
          />
          <label className="promo-toggle">
            <input type="checkbox" checked={showPromos} onChange={(e) => onTogglePromos(e.target.checked)} />
            Show promos
          </label>
          <RefreshButton onRefreshed={onRefreshed} />
        </div>
      </header>

      <ul className="list">
        {visible.map((email) => {
          const sender = sendersByAddress[email.from_address?.toLowerCase()]
          const bullets = (email.summary || '').split('\n').filter(Boolean)
          return (
            <li key={email.id} className="row">
              <Avatar label={email.from_name || email.from_address} />
              <div className="row-body">
                <div className="row-title">
                  <span className="row-subject">{email.subject || '(no subject)'}</span>
                  {email.classification && (
                    <span className={`badge ${LABEL_CLASS[email.classification] || ''}`}>
                      {email.classification}
                    </span>
                  )}
                  {sender?.is_cautious && <span className="badge badge-warn">wary</span>}
                </div>
                <div className="muted">
                  by {email.from_name || email.from_address || 'unknown'}
                  {email.received_at && ` · ${new Date(email.received_at).toLocaleDateString()}`}
                </div>
                {bullets.length > 0 ? (
                  <ul className="bullets">
                    {bullets.map((b, i) => (
                      <li key={i}>{b}</li>
                    ))}
                  </ul>
                ) : (
                  <div className="muted pending">Not analyzed yet</div>
                )}
              </div>
            </li>
          )
        })}
        {visible.length === 0 && (
          <li className="empty">{showPromos ? 'No emails here yet.' : 'Nothing important here right now.'}</li>
        )}
      </ul>
    </main>
  )
}

function SenderPanel({ category, senders, onSendersChanged }) {
  const [emailAddress, setEmailAddress] = useState('')
  const [error, setError] = useState(null)

  const categorySenders = senders.filter((s) => s.category === category)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)

    const res = await fetch(`${API_BASE}/senders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email_address: emailAddress, category, is_cautious: false }),
    })

    if (!res.ok) {
      const body = await res.json()
      setError(body.detail || 'Failed to add sender')
      return
    }

    setEmailAddress('')
    onSendersChanged()
  }

  async function handleToggleCautious(sender) {
    await fetch(`${API_BASE}/senders/${sender.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email_address: sender.email_address,
        category: sender.category,
        is_cautious: !sender.is_cautious,
      }),
    })
    onSendersChanged()
  }

  async function handleDelete(id) {
    await fetch(`${API_BASE}/senders/${id}`, { method: 'DELETE' })
    onSendersChanged()
  }

  return (
    <aside className="senders">
      <div className="senders-title">Senders</div>
      <form onSubmit={handleSubmit}>
        <input
          type="email"
          className="search"
          placeholder="+ Add a sender"
          value={emailAddress}
          onChange={(e) => setEmailAddress(e.target.value)}
          required
        />
      </form>
      {error && <p className="error">{error}</p>}
      <p className="muted panel-hint">Emails from these senders always land in this category.</p>

      <ul className="sender-list">
        {categorySenders.map((s) => (
          <li key={s.id} className="sender">
            <Avatar label={s.email_address} />
            <div className="sender-body">
              <div className="sender-name">{s.email_address.split('@')[0]}</div>
              <div className="muted">@{s.email_address.split('@')[1]}</div>
            </div>
            <button
              type="button"
              className={`icon-btn${s.is_cautious ? ' icon-btn-on' : ''}`}
              title={s.is_cautious ? 'Unmark wary' : 'Mark wary'}
              onClick={() => handleToggleCautious(s)}
            >
              ⚠
            </button>
            <button type="button" className="icon-btn" title="Remove" onClick={() => handleDelete(s.id)}>
              ×
            </button>
          </li>
        ))}
        {categorySenders.length === 0 && <li className="empty">No senders yet.</li>}
      </ul>
    </aside>
  )
}

function App() {
  const [senders, setSenders] = useState([])
  const [emails, setEmails] = useState([])
  const [selectedCategory, setActiveCategory] = useState(null)
  const [categories, setCategories] = useState([])
  const [query, setQuery] = useState('')
  const [showPromos, setShowPromos] = useState(false)

  async function fetchSenders() {
    const res = await fetch(`${API_BASE}/senders`)
    setSenders(await res.json())
  }

  async function fetchCategories() {
    const res = await fetch(`${API_BASE}/categories`)
    setCategories(await res.json())
  }

  async function fetchEmails(category, includePromos) {
    if (!category) {
      setEmails([])
      return
    }
    const params = new URLSearchParams({ category, include_promos: includePromos })
    const res = await fetch(`${API_BASE}/emails?${params}`)
    setEmails(await res.json())
  }

  useEffect(() => {
    fetchSenders()
    fetchCategories()
  }, [])

  // Default to the first category until the user picks one.
  const activeCategory = selectedCategory ?? categories[0]?.name ?? null

  useEffect(() => {
    fetchEmails(activeCategory, showPromos)
  }, [activeCategory, showPromos])

  const sendersByAddress = useMemo(
    () => Object.fromEntries(senders.map((s) => [s.email_address.toLowerCase(), s])),
    [senders],
  )

  async function handleAddCategory(name) {
    const res = await fetch(`${API_BASE}/categories`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
    if (!res.ok) return
    const created = await res.json()
    await fetchCategories()
    setActiveCategory(created.name)
  }

  return (
    <div className="shell">
      <Sidebar
        categories={categories}
        activeCategory={activeCategory}
        onSelect={setActiveCategory}
        onAddCategory={handleAddCategory}
      />
      {activeCategory ? (
        <>
          <EmailList
            emails={emails}
            sendersByAddress={sendersByAddress}
            category={activeCategory}
            query={query}
            onQuery={setQuery}
            showPromos={showPromos}
            onTogglePromos={setShowPromos}
            onRefreshed={() => {
              fetchEmails(activeCategory, showPromos)
              fetchCategories()
            }}
          />
          <SenderPanel category={activeCategory} senders={senders} onSendersChanged={fetchSenders} />
        </>
      ) : (
        <main className="main empty">Add a category to get started.</main>
      )}
    </div>
  )
}

export default App
