import { useEffect, useState } from 'react'
import { api, inr } from '../api.js'

export default function Redemption() {
  const [cards, setCards] = useState([])
  const [selected, setSelected] = useState('')
  const [advice, setAdvice] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.myCards().then((c) => {
      setCards(c)
      if (c.length) setSelected(String(c[0].id))
    }).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!selected) return
    setAdvice(null)
    api.redemptionAdvice(Number(selected)).then(setAdvice).catch((e) => setError(e.message))
  }, [selected])

  if (error) return <p className="text-red-600">{error}</p>
  if (!cards.length) return <p className="text-slate-500">Add a card first (My Cards tab).</p>

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold">Redemption Advisor</h2>
        <select value={selected} onChange={(e) => setSelected(e.target.value)}
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm">
          {cards.map((c) => <option key={c.id} value={c.id}>{c.display_name}</option>)}
        </select>
      </div>

      {!advice ? <p className="mt-4 text-slate-500">Loading…</p> : (
        <>
          <div className={`mt-4 rounded-xl border p-4 ${
            advice.decision.action === 'redeem'
              ? 'border-emerald-400 bg-emerald-50' : 'border-slate-300 bg-white'}`}>
            <div className="text-sm font-bold uppercase tracking-wide">
              {advice.decision.action === 'redeem' ? '→ Redeem now' : '⏳ Hold'}
            </div>
            {advice.decision.rationale.map((r, i) => (
              <p key={i} className="mt-1 text-sm text-slate-700">{r}</p>
            ))}
          </div>

          <div className="mt-4 grid grid-cols-3 gap-3 text-center">
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="text-xl font-bold">{advice.points_balance.toLocaleString('en-IN')}</div>
              <div className="text-xs text-slate-500">points balance</div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="text-xl font-bold">{inr(advice.fee_per_request_inr)}</div>
              <div className="text-xs text-slate-500">fee per request (incl. GST)</div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="text-xl font-bold">
                {Number.isFinite(advice.break_even_points)
                  ? advice.break_even_points.toLocaleString('en-IN') : '—'}
              </div>
              <div className="text-xs text-slate-500">break-even points / request</div>
            </div>
          </div>

          {advice.batching?.warn && (
            <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              ⚠ {advice.batching.recommendation}
            </p>
          )}
          {advice.batching && !advice.batching.warn && (
            <p className="mt-4 rounded-md bg-slate-100 px-3 py-2 text-sm text-slate-600">
              {advice.batching.recommendation}
            </p>
          )}

          {advice.expiry_alerts.map((a, i) => (
            <p key={i} className="mt-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
              ⏰ {a.message}
            </p>
          ))}

          <h3 className="mt-6 font-semibold">Options you can afford (net of fee)</h3>
          {!advice.ranked_options.length && (
            <p className="mt-2 text-sm text-slate-500">Nothing affordable yet — keep earning.</p>
          )}
          <table className="mt-2 w-full text-sm">
            <thead>
              <tr className="border-b border-slate-300 text-left text-xs text-slate-500">
                <th className="py-1.5">Option</th><th>Points</th><th>Net value</th><th>₹/pt</th>
              </tr>
            </thead>
            <tbody>
              {advice.ranked_options.map((o, i) => (
                <tr key={i} className="border-b border-slate-100">
                  <td className="py-2">{o.name} <span className="text-xs text-slate-400">({o.type})</span></td>
                  <td>{o.points_required.toLocaleString('en-IN')}</td>
                  <td>{inr(o.net_value_inr)}</td>
                  <td className="font-medium">{o.effective_value_per_point.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
