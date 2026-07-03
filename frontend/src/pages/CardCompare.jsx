import { useEffect, useState } from 'react'
import { api, inr } from '../api.js'

export default function CardCompare() {
  const [ltfOnly, setLtfOnly] = useState(false)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setData(null)
    api.recommend(ltfOnly).then(setData).catch((e) => setError(e.message))
  }, [ltfOnly])

  if (error) return <p className="text-red-600">{error}</p>
  if (!data) return <p className="text-slate-500">Simulating catalog on your spend…</p>
  if (!data.ranked.length)
    return <p className="text-slate-500">{data.note || 'Add some transactions first — the simulation runs on your real spend.'}</p>

  return (
    <div>
      <div className="flex flex-wrap items-center gap-4">
        <h2 className="text-lg font-semibold">Card Recommendation</h2>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={ltfOnly} onChange={(e) => setLtfOnly(e.target.checked)} />
          lifetime-free cards only
        </label>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Projected annual net value on your annualized spend profile:{' '}
        {Object.entries(data.spend_profile).map(([k, v]) => `${k.replaceAll('_', ' ')} ${inr(v)}`).join(' · ')}
      </p>

      <div className="mt-4 space-y-3">
        {data.ranked.map((r, i) => (
          <div key={r.card_id}
               className={`rounded-xl border bg-white p-4 shadow-sm ${
                 r.is_current ? 'border-sky-400 ring-1 ring-sky-200'
                 : i === 0 ? 'border-emerald-400 ring-1 ring-emerald-200' : 'border-slate-200'}`}>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="font-semibold">
                {i === 0 && !r.is_current &&
                  <span className="mr-2 rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">TOP PICK</span>}
                {r.is_current &&
                  <span className="mr-2 rounded bg-sky-100 px-2 py-0.5 text-xs text-sky-700">YOUR CARD</span>}
                {r.display_name}
              </h3>
              <div className="text-right">
                <span className="text-lg font-bold">{inr(r.annual_net_value)}/yr</span>
                {r.delta_vs_current_inr !== undefined && !r.is_current && (
                  <span className={`ml-2 text-sm font-medium ${
                    r.delta_vs_current_inr >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                    ({r.delta_vs_current_inr >= 0 ? '+' : ''}{inr(r.delta_vs_current_inr)})
                  </span>
                )}
              </div>
            </div>
            <p className="mt-1 text-xs">
              <span className={`rounded px-2 py-0.5 ${
                r.lifetime_free ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                {r.charges_flag}
              </span>
            </p>
            <p className="mt-2 text-xs text-slate-600">
              earn {inr(r.earn_inr)} + milestones {inr(r.milestone_inr)} + perks {inr(r.perks_inr)}
              {' '}− fee {inr(r.annual_fee_inr)} − joining (amortized) {inr(r.joining_fee_amortized_inr)}
            </p>
            {r.caveats.length > 0 && (
              <ul className="mt-2 list-inside list-disc text-xs text-amber-700">
                {r.caveats.slice(0, 4).map((c, j) => <li key={j}>{c}</li>)}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
