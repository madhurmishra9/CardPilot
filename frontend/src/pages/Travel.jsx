import { useEffect, useState } from 'react'
import { api, inr } from '../api.js'

export default function Travel() {
  const [form, setForm] = useState({ origin: 'BOM', dest: 'DEL', depart_date: '', return_date: '' })
  const [result, setResult] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [alertForm, setAlertForm] = useState({ route: 'BOM-DEL', target_price: '4000' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const refreshAlerts = () => api.fareAlerts().then(setAlerts)
  useEffect(() => { refreshAlerts() }, [])

  const search = async (e) => {
    e.preventDefault()
    setError(null); setBusy(true)
    try {
      setResult(await api.travelSearch({
        origin: form.origin, dest: form.dest, depart_date: form.depart_date,
        return_date: form.return_date || null,
      }))
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const addAlert = async (e) => {
    e.preventDefault()
    try {
      await api.addFareAlert({ route: alertForm.route, target_price: Number(alertForm.target_price) })
      refreshAlerts()
    } catch (err) { setError(err.message) }
  }

  const TREND_STYLE = {
    book_now: 'bg-emerald-50 border-emerald-400 text-emerald-800',
    book_soon: 'bg-amber-50 border-amber-400 text-amber-800',
    wait: 'bg-sky-50 border-sky-400 text-sky-800',
    insufficient_history: 'bg-slate-50 border-slate-300 text-slate-600',
  }

  return (
    <div className="max-w-3xl">
      <h2 className="text-lg font-semibold">Travel Savings</h2>
      <form onSubmit={search} className="mt-4 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        {['origin', 'dest'].map((f) => (
          <label key={f} className="text-sm">
            <span className="mb-1 block text-slate-600">{f === 'origin' ? 'From' : 'To'}</span>
            <input value={form[f]} maxLength="3"
                   onChange={(e) => setForm({ ...form, [f]: e.target.value.toUpperCase() })}
                   className="w-20 rounded-md border border-slate-300 px-3 py-2 uppercase" required />
          </label>
        ))}
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Depart</span>
          <input type="date" value={form.depart_date}
                 onChange={(e) => setForm({ ...form, depart_date: e.target.value })}
                 className="rounded-md border border-slate-300 px-3 py-2" required />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Return (optional)</span>
          <input type="date" value={form.return_date}
                 onChange={(e) => setForm({ ...form, return_date: e.target.value })}
                 className="rounded-md border border-slate-300 px-3 py-2" />
        </label>
        <button disabled={busy}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50">
          {busy ? 'Searching…' : 'Search fares'}
        </button>
      </form>
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {result && (
        <>
          <div className={`mt-4 rounded-xl border p-4 text-sm ${TREND_STYLE[result.trend.action]}`}>
            <b className="uppercase tracking-wide">{result.trend.action.replaceAll('_', ' ')}</b>
            <p className="mt-1">{result.trend.rationale}</p>
          </div>

          <h3 className="mt-5 font-semibold">Fares</h3>
          <table className="mt-2 w-full text-sm">
            <tbody>
              {result.fares.map((f, i) => (
                <tr key={i} className="border-b border-slate-100">
                  <td className="py-2">{f.carrier}</td>
                  <td>{f.origin} → {f.dest}</td>
                  <td className="font-medium">{inr(f.price_inr)}</td>
                  <td className="text-xs text-slate-400">{f.source}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {result.best_card.length > 0 && (
            <>
              <h3 className="mt-5 font-semibold">Best card for this booking</h3>
              {result.best_card.map((c, i) => (
                <div key={c.card_id} className={`mt-2 rounded-lg border bg-white p-3 text-sm ${
                  i === 0 ? 'border-emerald-400' : 'border-slate-200'}`}>
                  <div className="flex justify-between">
                    <b>{c.display_name}</b>
                    <span>effective cost <b>{inr(c.effective_cost_inr)}</b></span>
                  </div>
                  <p className="mt-1 text-xs text-slate-600">{c.explanation.join('; ')}</p>
                </div>
              ))}
            </>
          )}

          <h3 className="mt-5 font-semibold">Pay with cash or points?</h3>
          {Object.entries(result.points_vs_cash).map(([card, paths]) => (
            <div key={card} className="mt-2 rounded-lg border border-slate-200 bg-white p-3 text-sm">
              <b>{card}</b>
              <ul className="mt-1 space-y-1">
                {paths.map((p, i) => (
                  <li key={i} className={p.feasible ? '' : 'text-slate-400'}>
                    <span className="font-medium uppercase text-xs">{p.path}</span>{' '}
                    — {inr(p.effective_cost_inr)} · {p.explanation}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}

      <h3 className="mt-8 font-semibold">Fare alerts</h3>
      <p className="text-xs text-slate-500">Checked daily by the scheduler; you get a notification when a fare hits your target.</p>
      <form onSubmit={addAlert} className="mt-2 flex items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Route</span>
          <input value={alertForm.route} onChange={(e) => setAlertForm({ ...alertForm, route: e.target.value.toUpperCase() })}
                 placeholder="BOM-BKK" className="w-28 rounded-md border border-slate-300 px-3 py-2 uppercase" />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Target ₹</span>
          <input type="number" value={alertForm.target_price}
                 onChange={(e) => setAlertForm({ ...alertForm, target_price: e.target.value })}
                 className="w-28 rounded-md border border-slate-300 px-3 py-2" />
        </label>
        <button className="rounded-md border border-slate-900 px-4 py-2 text-sm font-semibold hover:bg-slate-100">Track</button>
      </form>
      <ul className="mt-3 space-y-2">
        {alerts.map((a) => (
          <li key={a.id} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm">
            <span><b>{a.route}</b> below {inr(a.target_price)}
              {a.last_notified && <span className="ml-2 text-xs text-emerald-600">✓ hit {a.last_notified.slice(0, 10)}</span>}
            </span>
            <button onClick={() => api.removeFareAlert(a.id).then(refreshAlerts)}
                    className="text-xs text-red-500 hover:underline">remove</button>
          </li>
        ))}
      </ul>
    </div>
  )
}
