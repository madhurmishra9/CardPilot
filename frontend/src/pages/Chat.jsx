import { useState } from 'react'
import { api } from '../api.js'

const SUGGESTIONS = [
  'Which card for ₹5k groceries?',
  'Should I redeem my points now?',
  'How close am I to the lounge benefit?',
  'Is there a better card for me?',
]

export default function Chat() {
  const shared = new URLSearchParams(window.location.search).get('text') || ''
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState(shared)
  const [busy, setBusy] = useState(false)

  const send = async (text) => {
    if (!text.trim() || busy) return
    setMessages((m) => [...m, { role: 'user', text }])
    setInput('')
    setBusy(true)
    try {
      const resp = await api.chat(text)
      setMessages((m) => [...m, { role: 'bot', text: resp.reply, intent: resp.intent, llm: resp.llm }])
    } catch (err) {
      setMessages((m) => [...m, { role: 'bot', text: `Error: ${err.message}` }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h2 className="text-lg font-semibold">Advisory Chat</h2>
      <p className="mt-1 text-xs text-slate-500">
        Every number comes from the deterministic engines — the model (if configured via
        CARDPILOT_LLM) only explains, it never does reward math.
      </p>

      <div className="mt-4 min-h-64 space-y-3 rounded-xl border border-slate-200 bg-white p-4">
        {messages.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => send(s)}
                      className="rounded-full border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100">
                {s}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === 'user' ? 'text-right' : ''}>
            <div className={`inline-block max-w-[85%] whitespace-pre-wrap rounded-xl px-4 py-2 text-sm ${
              m.role === 'user' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-800'}`}>
              {m.text}
            </div>
            {m.intent && (
              <div className="mt-0.5 text-[10px] text-slate-400">
                intent: {m.intent} · engine-grounded{m.llm !== 'none' ? ` · ${m.llm}` : ''}
              </div>
            )}
          </div>
        ))}
        {busy && <p className="text-sm text-slate-400">thinking…</p>}
      </div>

      <form onSubmit={(e) => { e.preventDefault(); send(input) }} className="mt-3 flex gap-2">
        <input value={input} onChange={(e) => setInput(e.target.value)}
               placeholder="Ask about swipes, redemptions, perks, or better cards…"
               className="flex-1 rounded-md border border-slate-300 px-4 py-2 text-sm" />
        <button disabled={busy}
                className="rounded-md bg-slate-900 px-5 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50">
          Send
        </button>
      </form>
    </div>
  )
}
