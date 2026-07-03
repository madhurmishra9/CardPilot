import { useEffect, useState } from 'react'
import { api, inr } from '../api.js'

function Gate({ gate }) {
  const pct = Math.min(100, (gate.current_spend / gate.gate_spend) * 100)
  return (
    <div className="mt-2">
      <div className="flex justify-between text-xs text-slate-500">
        <span>{gate.perk.replaceAll('_', ' ')}</span>
        <span>
          {gate.unlocked ? '✓ unlocked' : `${inr(gate.spend_needed)} to go`}
        </span>
      </div>
      <div className="mt-1 h-1.5 rounded bg-slate-200">
        <div
          className={`h-1.5 rounded ${gate.unlocked ? 'bg-emerald-500' : 'bg-amber-400'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

const NUDGE_STYLE = {
  high: 'bg-red-50 text-red-800',
  medium: 'bg-amber-50 text-amber-800',
  low: 'bg-slate-100 text-slate-600',
}

export default function Dashboard() {
  const [cards, setCards] = useState(null)
  const [nudges, setNudges] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    api.dashboard().then(setCards).catch((e) => setError(e.message))
    api.notifications().then((n) => setNudges(n.live)).catch(() => {})
  }, [])

  if (error) return <p className="text-red-600">{error}</p>
  if (!cards) return <p className="text-slate-500">Loading…</p>
  if (!cards.length)
    return (
      <p className="text-slate-500">
        No cards yet — add your first card in the <b>My Cards</b> tab.
      </p>
    )

  return (
    <div>
      {nudges.length > 0 && (
        <div className="mb-5 space-y-2">
          {nudges.map((n, i) => (
            <p key={i} className={`rounded-md px-3 py-2 text-sm ${NUDGE_STYLE[n.severity]}`}>
              {n.type === 'expiry' ? '⏰' : n.type === 'fare_drop' ? '✈️' : '🎯'} {n.message}
            </p>
          ))}
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2">
      {cards.map((c) => (
        <div key={c.user_card_id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-baseline justify-between">
            <h2 className="font-semibold">{c.display_name}</h2>
            <span className="text-xs text-slate-400">{c.card_id}</span>
          </div>
          <div className="mt-3 flex items-end gap-6">
            <div>
              <div className="text-2xl font-bold">{c.points_balance.toLocaleString('en-IN')}</div>
              <div className="text-xs text-slate-500">points ≈ {inr(c.points_value_inr)}</div>
            </div>
            <div>
              <div className="text-sm font-medium">{inr(c.year_spend)}</div>
              <div className="text-xs text-slate-500">spend this card-year</div>
            </div>
          </div>
          {c.next_milestone && (
            <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Spend {inr(c.next_milestone.spend_needed)} more to unlock{' '}
              <b>+{c.next_milestone.bonus_points.toLocaleString('en-IN')} bonus points</b>
            </p>
          )}
          {c.perk_gates.map((g) => (
            <Gate key={g.perk} gate={g} />
          ))}
          <p className="mt-3 text-xs text-slate-500">
            Annual fee this year:{' '}
            <b className={c.effective_annual_fee ? 'text-red-600' : 'text-emerald-600'}>
              {c.effective_annual_fee ? inr(c.effective_annual_fee) : 'waived / free'}
            </b>
          </p>
        </div>
      ))}
      </div>
    </div>
  )
}
