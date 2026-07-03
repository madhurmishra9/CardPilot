import { useEffect, useState } from 'react'
import { api, inr } from '../api.js'

export default function Cards() {
  const [catalog, setCatalog] = useState([])
  const [mine, setMine] = useState([])
  const [form, setForm] = useState({ card_id: '', last4: '', anniversary_month: 1 })
  const [error, setError] = useState(null)

  const refresh = () => Promise.all([api.catalog(), api.myCards()])
    .then(([cat, my]) => { setCatalog(cat); setMine(my); if (!form.card_id && cat.length) setForm((f) => ({ ...f, card_id: cat[0].card_id })) })

  useEffect(() => { refresh().catch((e) => setError(e.message)) }, [])

  const add = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      await api.addCard({ ...form, anniversary_month: Number(form.anniversary_month) })
      setForm({ ...form, last4: '' })
      refresh()
    } catch (err) { setError(err.message) }
  }

  return (
    <div className="max-w-3xl">
      <h2 className="text-lg font-semibold">My Cards</h2>
      {mine.length ? (
        <ul className="mt-3 space-y-2">
          {mine.map((c) => (
            <li key={c.id} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3">
              <span>
                <b>{c.display_name}</b>
                {c.last4 && <span className="ml-2 text-sm text-slate-500">•••• {c.last4}</span>}
              </span>
              <button onClick={() => api.removeCard(c.id).then(refresh)}
                      className="text-sm text-red-500 hover:underline">remove</button>
            </li>
          ))}
        </ul>
      ) : <p className="mt-3 text-sm text-slate-500">No cards yet.</p>}

      <form onSubmit={add} className="mt-4 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Card</span>
          <select value={form.card_id} onChange={(e) => setForm({ ...form, card_id: e.target.value })}
                  className="rounded-md border border-slate-300 bg-white px-3 py-2">
            {catalog.map((c) => <option key={c.card_id} value={c.card_id}>{c.display_name}</option>)}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Last 4 digits</span>
          <input value={form.last4} maxLength="4" pattern="\d{0,4}"
                 onChange={(e) => setForm({ ...form, last4: e.target.value })}
                 className="w-24 rounded-md border border-slate-300 px-3 py-2" placeholder="1234" />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Anniversary month</span>
          <input type="number" min="1" max="12" value={form.anniversary_month}
                 onChange={(e) => setForm({ ...form, anniversary_month: e.target.value })}
                 className="w-20 rounded-md border border-slate-300 px-3 py-2" />
        </label>
        <button className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700">Add card</button>
      </form>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      <h3 className="mt-8 font-semibold">Catalog ({catalog.length} cards)</h3>
      <p className="text-xs text-slate-500">Only the last 4 digits of a card are ever stored — never the full number.</p>
      <table className="mt-2 w-full text-sm">
        <thead>
          <tr className="border-b border-slate-300 text-left text-xs text-slate-500">
            <th className="py-1.5">Card</th><th>Issuer</th><th>Annual fee</th><th>Waiver at</th><th>Verified</th>
          </tr>
        </thead>
        <tbody>
          {catalog.map((c) => (
            <tr key={c.card_id} className="border-b border-slate-100">
              <td className="py-2">{c.display_name}</td>
              <td>{c.issuer}</td>
              <td>{c.lifetime_free ? <span className="text-emerald-600 font-medium">LTF</span> : inr(c.annual_fee)}</td>
              <td>{c.annual_fee_waiver_spend ? inr(c.annual_fee_waiver_spend) : '—'}</td>
              <td className="text-xs text-slate-400">{c.last_verified}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
