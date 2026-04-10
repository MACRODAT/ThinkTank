import React, { useState, useEffect, useCallback } from 'react'
import { getLoans, getMarketLoans, createLoan, repayLoan, listLoanOnMarket, buyLoan, getEconomyBalances } from '../../api'
import { useApp } from '../../context/AppContext'
import { COLORS, DEPT_IDS, DEPT_NAMES } from '../../constants'
import Spinner from '../../components/UI/Spinner'
import Modal from '../../components/UI/Modal'

function LoanCard({ loan, myDept, balances, onRepay, onList, onBuy, isFounder }) {
  const isLender   = loan.lender_dept   === myDept
  const isBorrower = loan.borrower_dept === myDept
  const myRole     = isLender ? '🏦 Lender' : isBorrower ? '💳 Borrower' : ''
  const outstanding = loan.outstanding || 0
  const principal   = loan.principal   || 0
  const pct         = principal > 0 ? Math.min(100, Math.round((1 - outstanding/principal)*100)) : 100
  const isOverdue   = loan.due_date && new Date(loan.due_date) < new Date()

  return (
    <div className="card" style={{ borderLeft: `4px solid ${isLender ? 'var(--green)' : 'var(--accent)'}` }}>
      <div style={{ display:'flex', gap:10, alignItems:'flex-start', marginBottom:10 }}>
        <div style={{ flex:1 }}>
          <div style={{ display:'flex', gap:8, alignItems:'center', marginBottom:4, flexWrap:'wrap' }}>
            <span className="dept-tag" style={{ background:COLORS[loan.lender_dept]||'#607D8B' }}>{loan.lender_dept}</span>
            <span style={{ fontSize:12, color:'var(--muted)' }}>→</span>
            <span className="dept-tag" style={{ background:COLORS[loan.borrower_dept]||'#607D8B' }}>{loan.borrower_dept}</span>
            {myRole && <span style={{ fontSize:10, fontWeight:700, color:'var(--muted)', marginLeft:4 }}>{myRole}</span>}
            {isOverdue && <span style={{ fontSize:10, fontWeight:800, color:'var(--red)', background:'rgba(248,81,73,.15)', padding:'1px 7px', borderRadius:4 }}>⚠ OVERDUE</span>}
            {loan.listed_on_market ? <span style={{ fontSize:10, fontWeight:700, color:'var(--orange)', background:'rgba(210,153,34,.12)', padding:'1px 7px', borderRadius:4 }}>🏪 On Market</span> : null}
            <span style={{ fontSize:10, fontWeight:700, color: loan.status==='active' ? 'var(--green)' : 'var(--muted)',
              textTransform:'uppercase', marginLeft:'auto' }}>{loan.status}</span>
          </div>
          <div style={{ fontSize:13 }}>
            <strong>{outstanding.toLocaleString()}</strong> pts outstanding
            <span style={{ color:'var(--muted)', fontSize:11 }}> / {principal.toLocaleString()} principal</span>
            <span style={{ color:'var(--orange)', fontSize:11, marginLeft:8 }}>@ {(loan.interest_rate*100).toFixed(1)}%/yr</span>
          </div>
          {loan.due_date && <div style={{ fontSize:11, color: isOverdue ? 'var(--red)' : 'var(--muted)', marginTop:2 }}>Due: {loan.due_date?.substring(0,10)}</div>}
          {/* Progress bar */}
          <div style={{ marginTop:8, height:5, borderRadius:3, background:'var(--border)', overflow:'hidden' }}>
            <div style={{ height:'100%', width:`${pct}%`, background:'var(--green)', borderRadius:3, transition:'width .5s' }} />
          </div>
          <div style={{ fontSize:10, color:'var(--muted)', marginTop:2 }}>{pct}% repaid</div>
        </div>
      </div>

      {loan.status === 'active' && (
        <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
          {isBorrower && (
            <button className="btn btn-success btn-sm" onClick={() => onRepay(loan)}>
              💰 Repay
            </button>
          )}
          {isLender && !loan.listed_on_market && (
            <button className="btn btn-outline btn-sm" onClick={() => onList(loan)}>
              🏪 List on Market
            </button>
          )}
          {!isLender && !isBorrower && loan.listed_on_market && (
            <button className="btn btn-primary btn-sm" onClick={() => onBuy(loan)}>
              🛒 Buy Loan ({loan.market_price} pts)
            </button>
          )}
          {isFounder && (
            <span style={{ fontSize:10, color:'var(--muted)', marginLeft:'auto', alignSelf:'center' }}>
              ID: {loan.id?.substring(0,8)}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

export default function LoansPage() {
  const { toast }  = useApp()
  const [myDept,   setMyDept]   = useState('HF')
  const [loans,    setLoans]    = useState([])
  const [market,   setMarket]   = useState([])
  const [bals,     setBals]     = useState({})
  const [loading,  setLoading]  = useState(true)
  const [tab,      setTab]      = useState('mine')

  // Create loan form
  const [createOpen,   setCreateOpen]   = useState(false)
  const [lenderDept,   setLenderDept]   = useState('HF')
  const [borrowerDept, setBorrowerDept] = useState('FIN')
  const [principal,    setPrincipal]    = useState(100)
  const [rate,         setRate]         = useState(10)
  const [dueDate,      setDueDate]      = useState('')
  const [listMarket,   setListMarket]   = useState(false)
  const [creating,     setCreating]     = useState(false)

  // Repay form
  const [repayLoan_,  setRepayLoan]  = useState(null)
  const [repayAmt,    setRepayAmt]   = useState(0)
  const [repaying,    setRepaying]   = useState(false)

  // List on market
  const [listLoan_,  setListLoan]   = useState(null)
  const [listPrice,  setListPrice]  = useState(0)

  const load = useCallback(async () => {
    setLoading(true)
    const [l, m, b] = await Promise.all([
      getLoans(myDept).catch(() => []),
      getMarketLoans().catch(() => []),
      getEconomyBalances().catch(() => ({})),
    ])
    setLoans(l); setMarket(m); setBals(b)
    setLoading(false)
  }, [myDept])

  useEffect(() => { load() }, [load])

  const doCreate = async () => {
    setCreating(true)
    const r = await createLoan({
      lender_dept: lenderDept, borrower_dept: borrowerDept,
      principal, interest_rate: rate / 100, due_date: dueDate,
      list_on_market: listMarket,
    }).catch(e => ({ error: e.message }))
    if (r.error) toast(r.error, 'error')
    else toast(`Loan created ✓ (${principal} pts @ ${rate}%)`)
    setCreating(false); setCreateOpen(false); load()
  }

  const doRepay = async () => {
    if (!repayLoan_) return
    setRepaying(true)
    const r = await repayLoan(repayLoan_.id, { amount: repayAmt, repayer_dept: myDept }).catch(e => ({ error: e.message }))
    if (r.error) toast(r.error, 'error')
    else toast(`Repaid ${repayAmt} pts ✓ (${r.remaining} remaining)`)
    setRepaying(false); setRepayLoan(null); load()
  }

  const doList = async () => {
    if (!listLoan_) return
    await listLoanOnMarket(listLoan_.id, { market_price: listPrice })
    toast('Loan listed on market ✓'); setListLoan(null); load()
  }

  const doBuy = async (loan) => {
    const r = await buyLoan(loan.id, { buyer_dept: myDept }).catch(e => ({ error: e.message }))
    if (r.error) toast(r.error, 'error')
    else toast(`You now own this loan ✓`)
    load()
  }

  const allLoans = tab === 'mine' ? loans : market

  return (
    <div>
      <div className="page-header" style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', flexWrap:'wrap', gap:12 }}>
        <div>
          <h2>🏦 Loans</h2>
          <p>Points loans between departments with interest. Buy and sell debt on the marketplace.</p>
        </div>
        <div style={{ display:'flex', gap:8, alignItems:'center' }}>
          <select className="form-control" style={{ maxWidth:100 }} value={myDept} onChange={e => setMyDept(e.target.value)}>
            {DEPT_IDS.map(d => <option key={d} value={d}>{d} ({bals[d]||0}pts)</option>)}
          </select>
          <button className="btn btn-primary" onClick={() => { setLenderDept('founder'); setCreateOpen(true) }}>
            + New Loan
          </button>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${tab==='mine'?' active':''}`} onClick={() => setTab('mine')}>
          My Loans {loans.length > 0 && <span className="badge" style={{ marginLeft:4, background:'var(--accent)' }}>{loans.length}</span>}
        </button>
        <button className={`tab${tab==='market'?' active':''}`} onClick={() => setTab('market')}>
          🏪 Loan Market {market.length > 0 && <span className="badge" style={{ marginLeft:4 }}>{market.length}</span>}
        </button>
      </div>

      {loading ? <div className="empty"><Spinner /></div>
        : allLoans.length === 0 ? (
          <div className="empty">
            {tab === 'mine' ? 'No loans for this department.' : 'No loans on the market.'}
            <button className="btn btn-outline" style={{ marginTop:12 }} onClick={() => setCreateOpen(true)}>
              + Create Loan
            </button>
          </div>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
            {allLoans.map(l => (
              <LoanCard key={l.id} loan={l} myDept={myDept} balances={bals}
                isFounder={false}
                onRepay={l => { setRepayLoan(l); setRepayAmt(Math.min(l.outstanding, bals[myDept]||0)) }}
                onList={l  => { setListLoan(l);  setListPrice(l.outstanding) }}
                onBuy={doBuy}
              />
            ))}
          </div>
        )}

      {/* Create loan modal */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)}>
        <h3 style={{ marginBottom:16 }}>+ Create Loan</h3>
        <div className="form-row form-row-2">
          <div className="form-group">
            <label className="form-label">Lender</label>
            <select className="form-control" value={lenderDept} onChange={e => setLenderDept(e.target.value)}>
              <option value="founder">Founder (you)</option>
              {DEPT_IDS.map(d => <option key={d} value={d}>{d} ({bals[d]||0}pts)</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Borrower</label>
            <select className="form-control" value={borrowerDept} onChange={e => setBorrowerDept(e.target.value)}>
              {DEPT_IDS.map(d => <option key={d} value={d}>{d} ({bals[d]||0}pts)</option>)}
            </select>
          </div>
        </div>
        <div className="form-row form-row-2">
          <div className="form-group">
            <label className="form-label">Principal (pts)</label>
            <input type="number" className="form-control" min={1} value={principal}
              onChange={e => setPrincipal(Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label className="form-label">Annual Interest Rate (%)</label>
            <input type="number" className="form-control" min={0} max={1000} step={0.5} value={rate}
              onChange={e => setRate(Number(e.target.value))} />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Due Date (optional)</label>
          <input type="date" className="form-control" value={dueDate} onChange={e => setDueDate(e.target.value)} />
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:14 }}>
          <input type="checkbox" id="list-mkt" checked={listMarket} onChange={e => setListMarket(e.target.checked)} />
          <label htmlFor="list-mkt" style={{ fontSize:12, cursor:'pointer' }}>
            List on marketplace immediately (others can buy this loan)
          </label>
        </div>
        <div style={{ fontSize:12, color:'var(--muted)', marginBottom:14, padding:'8px 12px',
          background:'rgba(88,166,255,.06)', borderRadius:6 }}>
          Daily interest ≈ {Math.max(1, Math.round(principal * rate / 100 / 365))} pts/day
          on {principal} pts @ {rate}%/yr
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-success" onClick={doCreate} disabled={creating || principal <= 0}>
            {creating ? <Spinner /> : '✓ Create Loan'}
          </button>
          <button className="btn btn-ghost" onClick={() => setCreateOpen(false)}>Cancel</button>
        </div>
      </Modal>

      {/* Repay modal */}
      <Modal open={!!repayLoan_} onClose={() => setRepayLoan(null)}>
        <h3 style={{ marginBottom:14 }}>💰 Repay Loan</h3>
        {repayLoan_ && (
          <>
            <div style={{ fontSize:13, marginBottom:14 }}>
              Outstanding: <strong>{repayLoan_.outstanding} pts</strong>
              &nbsp;to <span className="dept-tag" style={{ background:COLORS[repayLoan_.lender_dept]||'#607D8B' }}>{repayLoan_.lender_dept}</span>
            </div>
            <div className="form-group">
              <label className="form-label">Amount to Repay</label>
              <div style={{ display:'flex', gap:8, alignItems:'center' }}>
                <input type="range" min={1} max={Math.min(repayLoan_.outstanding, bals[myDept]||0)}
                  value={repayAmt} onChange={e => setRepayAmt(Number(e.target.value))}
                  style={{ flex:1, accentColor:'var(--accent)' }} />
                <input type="number" className="form-control" style={{ width:90 }} min={1}
                  max={Math.min(repayLoan_.outstanding, bals[myDept]||0)}
                  value={repayAmt} onChange={e => setRepayAmt(Number(e.target.value))} />
              </div>
              <div style={{ fontSize:11, color:'var(--muted)', marginTop:4 }}>
                Your balance: {bals[myDept]||0} pts
              </div>
            </div>
            <div style={{ display:'flex', gap:8 }}>
              <button className="btn btn-success" onClick={doRepay} disabled={repaying || repayAmt <= 0}>
                {repaying ? <Spinner /> : `Repay ${repayAmt} pts`}
              </button>
              <button className="btn btn-primary btn-sm"
                onClick={() => setRepayAmt(Math.min(repayLoan_.outstanding, bals[myDept]||0))}>
                Pay All
              </button>
              <button className="btn btn-ghost" onClick={() => setRepayLoan(null)}>Cancel</button>
            </div>
          </>
        )}
      </Modal>

      {/* List on market modal */}
      <Modal open={!!listLoan_} onClose={() => setListLoan(null)}>
        <h3 style={{ marginBottom:14 }}>🏪 List Loan on Market</h3>
        {listLoan_ && (
          <>
            <div style={{ fontSize:12, color:'var(--muted)', marginBottom:12 }}>
              Borrower owes <strong>{listLoan_.outstanding} pts</strong> at {(listLoan_.interest_rate*100).toFixed(1)}%/yr.
              You'll receive pts upfront; buyer collects future repayments.
            </div>
            <div className="form-group">
              <label className="form-label">Listing Price (pts you want upfront)</label>
              <input type="number" className="form-control" min={1} value={listPrice}
                onChange={e => setListPrice(Number(e.target.value))} />
              <div style={{ fontSize:11, color:'var(--muted)', marginTop:4 }}>
                Discount from outstanding ({listLoan_.outstanding}): {listLoan_.outstanding - listPrice} pts
              </div>
            </div>
            <div style={{ display:'flex', gap:8 }}>
              <button className="btn btn-success" onClick={doList}>List for {listPrice} pts</button>
              <button className="btn btn-ghost" onClick={() => setListLoan(null)}>Cancel</button>
            </div>
          </>
        )}
      </Modal>
    </div>
  )
}
