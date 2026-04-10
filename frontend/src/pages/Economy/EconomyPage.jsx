import React, { useState, useEffect, useCallback } from 'react'
import { getEconomyBalances, getDeptLedger, economyAdjust, economyTransfer, getSearchMetrics } from '../../api'
import { useApp } from '../../context/AppContext'
import { COLORS, DEPT_IDS, DEPT_NAMES } from '../../constants'
import Spinner from '../../components/UI/Spinner'

const COST_REFERENCE = [
  { action: 'Weekly allocation (Fridays 22:00)', pts: '+200', color: 'var(--green)' },
  { action: 'Strategy draft create (CEO)', pts: '-80', color: 'var(--red)' },
  { action: 'Strategy draft create (agent)', pts: '-160', color: 'var(--red)' },
  { action: 'Strategy draft approved', pts: '+180', color: 'var(--green)' },
  { action: 'Strategy draft revised (per edit)', pts: '-2', color: 'var(--orange)' },
  { action: 'Strategy draft scrapped', pts: '-20', color: 'var(--red)' },
  { action: 'Strategy draft overdue (per day)', pts: '-5', color: 'var(--orange)' },
  { action: 'Other draft create', pts: '-20', color: 'var(--red)' },
  { action: 'Other draft approved', pts: '+2', color: 'var(--green)' },
  { action: 'Founder rejects approved draft', pts: '-80', color: 'var(--red)' },
  { action: 'Draft revision/edit award', pts: '+1', color: 'var(--green)' },
  { action: 'Message to Founder', pts: '-35', color: 'var(--red)' },
  { action: 'Endeavor rejected (CEO)', pts: '-125', color: 'var(--red)' },
  { action: 'Endeavor rejected (agent)', pts: '-180', color: 'var(--red)' },
  { action: 'Endeavor approved (CEO)', pts: '+150', color: 'var(--green)' },
  { action: 'New agent spawned', pts: '-50', color: 'var(--red)' },
  { action: 'Web search (per call)', pts: '-10', color: 'var(--orange)' },
  { action: 'CEO mail to other CEO', pts: '-1 / +1', color: 'var(--muted)' },
  { action: 'CEO mail to other agent', pts: '-2 / +2', color: 'var(--muted)' },
  { action: 'Agent mail to other agent', pts: '-1 / +1', color: 'var(--muted)' },
  { action: 'Agent mail to other CEO', pts: '-10 / +10', color: 'var(--red)' },
  { action: 'Agent heartbeat', pts: '-1', color: 'var(--orange)' },
  { action: 'CEO heartbeat', pts: '-5', color: 'var(--orange)' },
  { action: 'CEO chat with Founder', pts: '-20', color: 'var(--red)' },
  { action: 'Tool: get_time', pts: '-2', color: 'var(--orange)' },
  { action: 'Tool: check_offline', pts: '-10', color: 'var(--orange)' },
]

function BalanceBar({ dept, balance, max }) {
  const pct    = max > 0 ? Math.max(0, Math.min(100, (balance / max) * 100)) : 0
  const color  = balance < 0 ? 'var(--red)' : balance < 50 ? 'var(--orange)' : 'var(--green)'
  return (
    <div style={{ display:'flex', alignItems:'center', gap:12, padding:'10px 0', borderBottom:'1px solid var(--border)' }}>
      <div style={{ width:36, height:36, borderRadius:8, background:COLORS[dept]||'#607D8B',
        display:'flex', alignItems:'center', justifyContent:'center', fontSize:11, fontWeight:800, color:'#fff', flexShrink:0 }}>
        {dept}
      </div>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ display:'flex', justifyContent:'space-between', marginBottom:4 }}>
          <span style={{ fontSize:12, fontWeight:600 }}>{DEPT_NAMES[dept]||dept}</span>
          <span style={{ fontSize:13, fontWeight:800, color }}>{balance} pts</span>
        </div>
        <div style={{ height:6, borderRadius:3, background:'var(--border)', overflow:'hidden' }}>
          <div style={{ height:'100%', width:`${pct}%`, background:color, borderRadius:3, transition:'width 0.5s ease' }} />
        </div>
      </div>
    </div>
  )
}

export default function EconomyPage() {
  const { toast } = useApp()
  const [balances,  setBalances]  = useState({})
  const [ledger,    setLedger]    = useState([])
  const [ledgerDept,setLedgerDept]= useState('')
  const [metrics,   setMetrics]   = useState([])
  const [tab,       setTab]       = useState('overview')
  const [loading,   setLoading]   = useState(true)

  // Adjust form
  const [adjDept,  setAdjDept]  = useState('HF')
  const [adjPts,   setAdjPts]   = useState(0)
  const [adjNote,  setAdjNote]  = useState('')
  const [adjBusy,  setAdjBusy]  = useState(false)

  // Transfer form
  const [trFrom,   setTrFrom]   = useState('HF')
  const [trTo,     setTrTo]     = useState('FIN')
  const [trPts,    setTrPts]    = useState(0)
  const [trNote,   setTrNote]   = useState('')
  const [trBusy,   setTrBusy]   = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    const b = await getEconomyBalances().catch(() => ({}))
    setBalances(b)
    const m = await getSearchMetrics(50).catch(() => [])
    setMetrics(m)
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const loadLedger = async (dept) => {
    setLedgerDept(dept)
    const l = await getDeptLedger(dept, 50).catch(() => [])
    setLedger(l)
  }

  const doAdjust = async () => {
    setAdjBusy(true)
    await economyAdjust({ dept_id: adjDept, points: adjPts, note: adjNote })
    toast(`${adjPts > 0 ? 'Awarded' : 'Deducted'} ${Math.abs(adjPts)} pts to ${adjDept} ✓`)
    setAdjBusy(false); setAdjNote(''); load()
    if (ledgerDept === adjDept) loadLedger(adjDept)
  }

  const doTransfer = async () => {
    if (trFrom === trTo) { toast('Cannot transfer to same dept', 'error'); return }
    setTrBusy(true)
    const r = await economyTransfer({ from_dept: trFrom, to_dept: trTo, points: trPts, note: trNote }).catch(e => ({ error: e.message }))
    if (r.error) toast(r.error, 'error')
    else toast(`Transferred ${trPts} pts from ${trFrom} → ${trTo} ✓`)
    setTrBusy(false); setTrNote(''); load()
  }

  const maxBal = Math.max(1, ...Object.values(balances).map(v => Math.abs(v)))
  const sorted = Object.entries(balances).sort((a, b) => b[1] - a[1])

  return (
    <div>
      <div className="page-header">
        <h2>💰 Points Economy</h2>
        <p>Department point balances, transactions, and web search costs</p>
      </div>

      <div className="tabs">
        {['overview','ledger','search','rules'].map(t => (
          <button key={t} className={`tab${tab===t?' active':''}`} onClick={() => setTab(t)}>
            {{ overview:'📊 Overview', ledger:'📒 Ledger', search:'🔍 Search Metrics', rules:'📋 Rules' }[t]}
          </button>
        ))}
      </div>

      {loading && tab !== 'rules' ? <div className="empty"><Spinner /></div> : (

        tab === 'overview' ? (
          <div style={{ display:'grid', gap:20, gridTemplateColumns:'1fr 1fr' }}>
            {/* Balances */}
            <div className="card">
              <div className="card-header"><span className="card-title">Department Balances</span></div>
              {sorted.map(([dept, bal]) => (
                <div key={dept} onClick={() => { setTab('ledger'); loadLedger(dept) }} style={{ cursor:'pointer' }}>
                  <BalanceBar dept={dept} balance={bal} max={maxBal} />
                </div>
              ))}
            </div>

            {/* Founder controls */}
            <div>
              <div className="card" style={{ marginBottom:16 }}>
                <div className="card-header"><span className="card-title">⚡ Manual Adjust</span></div>
                <div style={{ display:'flex', gap:8, flexWrap:'wrap', alignItems:'flex-end' }}>
                  <div>
                    <div className="form-label">Department</div>
                    <select className="form-control" style={{ width:100 }} value={adjDept} onChange={e => setAdjDept(e.target.value)}>
                      {DEPT_IDS.map(d => <option key={d} value={d}>{d}</option>)}
                    </select>
                  </div>
                  <div>
                    <div className="form-label">Points (+/−)</div>
                    <input type="number" className="form-control" style={{ width:100 }}
                      value={adjPts} onChange={e => setAdjPts(Number(e.target.value))} />
                  </div>
                  <div style={{ flex:1 }}>
                    <div className="form-label">Note</div>
                    <input className="form-control" placeholder="Reason…" value={adjNote} onChange={e => setAdjNote(e.target.value)} />
                  </div>
                  <button className="btn btn-primary" onClick={doAdjust} disabled={adjBusy || adjPts === 0}>
                    {adjBusy ? <Spinner /> : '⚡ Apply'}
                  </button>
                </div>
              </div>

              <div className="card">
                <div className="card-header"><span className="card-title">🔄 Transfer Between Depts</span></div>
                <div style={{ display:'flex', gap:8, flexWrap:'wrap', alignItems:'flex-end' }}>
                  <div>
                    <div className="form-label">From</div>
                    <select className="form-control" style={{ width:80 }} value={trFrom} onChange={e => setTrFrom(e.target.value)}>
                      {DEPT_IDS.map(d => <option key={d} value={d}>{d}</option>)}
                    </select>
                  </div>
                  <div>
                    <div className="form-label">To</div>
                    <select className="form-control" style={{ width:80 }} value={trTo} onChange={e => setTrTo(e.target.value)}>
                      {DEPT_IDS.map(d => <option key={d} value={d}>{d}</option>)}
                    </select>
                  </div>
                  <div>
                    <div className="form-label">Points</div>
                    <input type="number" className="form-control" style={{ width:80 }} min={1}
                      value={trPts} onChange={e => setTrPts(Number(e.target.value))} />
                  </div>
                  <div style={{ flex:1 }}>
                    <div className="form-label">Note</div>
                    <input className="form-control" placeholder="Transfer reason…" value={trNote} onChange={e => setTrNote(e.target.value)} />
                  </div>
                  <button className="btn btn-success" onClick={doTransfer} disabled={trBusy || trPts <= 0}>
                    {trBusy ? <Spinner /> : '↔ Transfer'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )

        : tab === 'ledger' ? (
          <div>
            <div style={{ display:'flex', gap:8, marginBottom:16, flexWrap:'wrap' }}>
              {DEPT_IDS.map(d => (
                <button key={d} className={`btn btn-sm ${ledgerDept===d?'btn-primary':'btn-outline'}`}
                  onClick={() => loadLedger(d)}
                  style={{ borderColor: COLORS[d] }}>
                  {d}
                </button>
              ))}
            </div>
            {!ledgerDept ? (
              <div className="empty">Select a department to view its transaction history.</div>
            ) : (
              <div className="card" style={{ padding:0 }}>
                <div style={{ padding:'12px 16px', borderBottom:'1px solid var(--border)', display:'flex', justifyContent:'space-between' }}>
                  <strong>{DEPT_NAMES[ledgerDept]} ledger</strong>
                  <strong style={{ color: (balances[ledgerDept]||0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    Balance: {balances[ledgerDept]||0} pts
                  </strong>
                </div>
                {ledger.length === 0 ? <div className="empty">No transactions yet.</div> : ledger.map(tx => (
                  <div key={tx.id} style={{ display:'flex', gap:12, padding:'10px 16px', borderBottom:'1px solid var(--border)', alignItems:'center' }}>
                    <span style={{ fontSize:11, color:'var(--muted)', flexShrink:0, width:130 }}>
                      {tx.created_at?.substring(0,16).replace('T',' ')}
                    </span>
                    <span style={{ flex:1, fontSize:12 }}>{tx.event}</span>
                    <span style={{ fontSize:11, color:'var(--muted)', flex:2, minWidth:0 }}>{tx.note}</span>
                    <span style={{ fontWeight:700, fontSize:13, color: tx.delta > 0 ? 'var(--green)' : 'var(--red)', flexShrink:0, width:60, textAlign:'right' }}>
                      {tx.delta > 0 ? '+' : ''}{tx.delta}
                    </span>
                    <span style={{ fontSize:12, color:'var(--muted)', flexShrink:0, width:60, textAlign:'right' }}>
                      {tx.balance}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )

        : tab === 'search' ? (
          <div className="card" style={{ padding:0 }}>
            <div style={{ padding:'12px 16px', borderBottom:'1px solid var(--border)', fontSize:13, color:'var(--muted)' }}>
              {metrics.length} search calls logged · Each costs 10 pts
            </div>
            {metrics.length === 0 ? <div className="empty">No web searches yet.</div> : metrics.map(m => (
              <div key={m.id} style={{ display:'flex', gap:10, padding:'10px 16px', borderBottom:'1px solid var(--border)', alignItems:'center', flexWrap:'wrap' }}>
                <span style={{ fontSize:10, color:'var(--muted)', flexShrink:0 }}>{m.created_at?.substring(0,16).replace('T',' ')}</span>
                <span className="dept-tag" style={{ background:COLORS[m.dept_id]||'#607D8B', fontSize:9 }}>{m.dept_id}</span>
                <span style={{ fontSize:12, fontWeight:600, flex:1 }}>{m.agent_name}</span>
                <span style={{ fontSize:12, flex:2, color:'var(--muted)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{m.query}</span>
                <span style={{ fontSize:11, color:'var(--muted)', flexShrink:0 }}>{m.provider}</span>
                <span style={{ fontSize:10, color: m.success ? 'var(--green)' : 'var(--red)', flexShrink:0, fontWeight:700 }}>
                  {m.success ? '✓' : '✗'}
                </span>
              </div>
            ))}
          </div>
        )

        : (
          <div className="card">
            <div className="card-header"><span className="card-title">📋 Points Cost Reference</span></div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'2px 16px' }}>
              {COST_REFERENCE.map((r,i) => (
                <div key={i} style={{ display:'flex', justifyContent:'space-between', padding:'7px 0', borderBottom:'1px solid var(--border)', gap:8 }}>
                  <span style={{ fontSize:12, color:'var(--muted)' }}>{r.action}</span>
                  <span style={{ fontSize:12, fontWeight:700, color:r.color, flexShrink:0 }}>{r.pts}</span>
                </div>
              ))}
            </div>
          </div>
        )
      )}
    </div>
  )
}
