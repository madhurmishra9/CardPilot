import { useEffect, useState } from 'react'
import { api, CATEGORIES, inr } from '../api.js'

export default function Transactions() {
  const [cards, setCards] = useState([])
  const [txns, setTxns] = useState([])
  const [form, setForm] = useState({ amount: '', merchant: '', category_key: '', date: new Date().toISOString().slice(0, 10) })
  const [csv, setCsv] = useState({ files: [], date: 'Txn Date', amount: 'Amount', merchant: 'Details' })
  const [cardId, setCardId] = useState('')
  const [msg, setMsg] = useState(null)
  const [mappings, setMappings] = useState([])
  const [mappingName, setMappingName] = useState('')
  const [fileInputKey, setFileInputKey] = useState(0)

  const refresh = () => api.transactions().then(setTxns)
  const refreshMappings = () => api.csvMappings().then(setMappings).catch(() => {})

  useEffect(() => {
    api.myCards().then((c) => {
      setCards(c)
      if (c.length) setCardId(String(c[0].id))
    })
    refresh()
    refreshMappings()
  }, [])

  const applyMapping = (id) => {
    const m = mappings.find((x) => String(x.id) === id)
    if (m) setCsv({ ...csv, date: m.mapping.date || '', amount: m.mapping.amount || '', merchant: m.mapping.merchant || '' })
  }

  const saveMapping = async () => {
    if (!mappingName.trim()) { setMsg('Give the mapping a name first (e.g. "ICICI export")'); return }
    await api.saveCsvMapping({ name: mappingName, mapping: { date: csv.date, amount: csv.amount, merchant: csv.merchant } })
    setMsg(`Mapping '${mappingName}' saved — map once, reuse forever`)
    refreshMappings()
  }

  const submit = async (e) => {
    e.preventDefault()
    setMsg(null)
    try {
      const res = await api.addTransaction({
        user_card_id: Number(cardId),
        date: form.date,
        amount: Number(form.amount),
        merchant: form.merchant,
        category_key: form.category_key || null,
      })
      setMsg(`Added — categorized as '${res.category_key}', earned ${res.points_earned} pts`)
      setForm({ ...form, amount: '', merchant: '' })
      refresh()
    } catch (err) { setMsg(err.message) }
  }

  const upload = async (e) => {
    e.preventDefault()
    if (!csv.files.length) return
    setMsg(null)
    let imported = 0
    let points = 0
    const failures = []
    for (const file of csv.files) {
      const fd = new FormData()
      fd.append('user_card_id', cardId)
      fd.append('parser', file.name.endsWith('.pdf') ? 'icici_pdf' : 'generic_csv')
      fd.append('mapping', JSON.stringify({ date: csv.date, amount: csv.amount, merchant: csv.merchant }))
      fd.append('file', file)
      try {
        const res = await api.uploadStatement(fd)
        imported += res.imported
        points += res.points_earned
      } catch (err) {
        failures.push(`${file.name}: ${err.message}`)
      }
    }
    const fileWord = csv.files.length === 1 ? 'file' : 'files'
    let summary = `Imported ${imported} transactions (+${points} pts) from ${csv.files.length} ${fileWord}`
    if (failures.length) summary += ` — failed: ${failures.join('; ')}`
    setMsg(summary)
    setCsv({ ...csv, files: [] })
    setFileInputKey((k) => k + 1)
    refresh()
  }

  const recategorize = async (t, key) => {
    await api.correctCategory(t.id, { category_key: key, remember: true })
    refresh()
  }

  if (!cards.length) return <p className="text-slate-500">Add a card first (My Cards tab).</p>

  return (
    <div>
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold">Transactions</h2>
        <select value={cardId} onChange={(e) => setCardId(e.target.value)}
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm">
          {cards.map((c) => <option key={c.id} value={c.id}>{c.display_name}</option>)}
        </select>
      </div>

      <form onSubmit={submit} className="mt-4 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Date</span>
          <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })}
                 className="rounded-md border border-slate-300 px-3 py-2" required />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Amount (₹)</span>
          <input type="number" min="1" step="0.01" value={form.amount}
                 onChange={(e) => setForm({ ...form, amount: e.target.value })}
                 className="w-28 rounded-md border border-slate-300 px-3 py-2" required />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Merchant</span>
          <input value={form.merchant} onChange={(e) => setForm({ ...form, merchant: e.target.value })}
                 className="w-44 rounded-md border border-slate-300 px-3 py-2" placeholder="e.g. Swiggy" />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Category</span>
          <select value={form.category_key} onChange={(e) => setForm({ ...form, category_key: e.target.value })}
                  className="rounded-md border border-slate-300 bg-white px-3 py-2">
            <option value="">auto-detect</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c.replaceAll('_', ' ')}</option>)}
          </select>
        </label>
        <button className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700">Add</button>
      </form>

      <form onSubmit={upload} className="mt-3 flex flex-wrap items-end gap-3 rounded-xl border border-dashed border-slate-300 bg-white p-4">
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Statement(s) (CSV / ICICI PDF)</span>
          <input key={fileInputKey} type="file" accept=".csv,.pdf" multiple
                 onChange={(e) => setCsv({ ...csv, files: Array.from(e.target.files) })}
                 className="text-sm" />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Date column</span>
          <input value={csv.date} onChange={(e) => setCsv({ ...csv, date: e.target.value })}
                 className="w-28 rounded-md border border-slate-300 px-3 py-2" />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Amount column</span>
          <input value={csv.amount} onChange={(e) => setCsv({ ...csv, amount: e.target.value })}
                 className="w-28 rounded-md border border-slate-300 px-3 py-2" />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Merchant column</span>
          <input value={csv.merchant} onChange={(e) => setCsv({ ...csv, merchant: e.target.value })}
                 className="w-28 rounded-md border border-slate-300 px-3 py-2" />
        </label>
        <button className="rounded-md border border-slate-900 px-4 py-2 text-sm font-semibold hover:bg-slate-100">Upload</button>
        <div className="flex w-full flex-wrap items-end gap-3 border-t border-slate-100 pt-3">
          {mappings.length > 0 && (
            <label className="text-sm">
              <span className="mb-1 block text-slate-600">Saved mappings</span>
              <select defaultValue="" onChange={(e) => applyMapping(e.target.value)}
                      className="rounded-md border border-slate-300 bg-white px-3 py-2">
                <option value="" disabled>apply a saved mapping…</option>
                {mappings.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </label>
          )}
          <label className="text-sm">
            <span className="mb-1 block text-slate-600">Save current mapping as</span>
            <input value={mappingName} onChange={(e) => setMappingName(e.target.value)}
                   placeholder="e.g. ICICI export"
                   className="w-40 rounded-md border border-slate-300 px-3 py-2" />
          </label>
          <button type="button" onClick={saveMapping}
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100">
            Save mapping
          </button>
        </div>
      </form>

      {msg && <p className="mt-3 text-sm text-slate-600">{msg}</p>}

      <table className="mt-4 w-full text-sm">
        <thead>
          <tr className="border-b border-slate-300 text-left text-xs text-slate-500">
            <th className="py-1.5">Date</th><th>Merchant</th><th>Amount</th>
            <th>Category (click to fix)</th><th>Points</th><th>Source</th>
          </tr>
        </thead>
        <tbody>
          {txns.map((t) => (
            <tr key={t.id} className="border-b border-slate-100">
              <td className="py-2">{t.date}</td>
              <td>{t.merchant || '—'}</td>
              <td>{inr(t.amount)}</td>
              <td>
                <select value={t.category_key} onChange={(e) => recategorize(t, e.target.value)}
                        className="rounded border border-transparent bg-transparent text-sm hover:border-slate-300">
                  {CATEGORIES.map((c) => <option key={c} value={c}>{c.replaceAll('_', ' ')}</option>)}
                </select>
              </td>
              <td className={t.is_reward_eligible ? '' : 'text-slate-400'}>
                {t.points_earned}{!t.is_reward_eligible && ' (excluded)'}
              </td>
              <td className="text-xs text-slate-400">{t.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
