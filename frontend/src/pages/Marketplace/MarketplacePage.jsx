import React, { useState, useEffect, useCallback } from 'react'
import {
  getMarketAgents, listAgentForSale, buyMarketAgent, fireAgentToPool,
  getMarketExtensions, listExtForSale, buyMarketExtension,
  getEconomyBalances, getAgents,
} from '../../api'
import { useApp } from '../../context/AppContext'
import { COLORS, DEPT_IDS, DEPT_NAMES } from '../../constants'
import Spinner from '../../components/UI/Spinner'
import Modal from '../../components/UI/Modal'

// ── Agent card ────────────────────────────────────────────────────────────────
function AgentCard({ listing, balances, onBuy, isBuying }) {
  const [buyDept, setBuyDept] = useState('HF')
  const [open,    setOpen]    = useState(false)
  const bal  = balances[buyDept] || 0
  const cost = listing.price || 0
  const free = cost === 0

  return (
    <div className="card" style={{ position:'relative' }}>
      {free && (
        <span style={{ position:'absolute', top:10, right:10, fontSize:9, fontWeight:800,
          background:'rgba(63,185,80,.2)', color:'var(--green)', padding:'2px 7px', borderRadius:4 }}>
          FREE
        </span>
      )}
      <div style={{ display:'flex', gap:12, alignItems:'flex-start', marginBottom:10 }}>
        <div style={{ width:44, height:44, borderRadius:'50%', overflow:'hidden',
          background: COLORS[listing.current_dept]||'#607D8B', flexShrink:0,
          display:'flex', alignItems:'center', justifyContent:'center', fontSize:16, fontWeight:800, color:'#fff' }}>
          {listing.profile_image_url
            ? <img src={listing.profile_image_url} style={{ width:'100%', height:'100%', objectFit:'cover' }} />
            : listing.name?.[0]}
        </div>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ fontSize:14, fontWeight:700 }}>{listing.name}</div>
          <div style={{ fontSize:11, color:'var(--muted)' }}>{listing.role} · {listing.title}</div>
          <div style={{ fontSize:11, color:'var(--muted)', marginTop:2 }}>
            Listed by: <span className="dept-tag" style={{ background:COLORS[listing.seller_dept]||'#607D8B', fontSize:9 }}>{listing.seller_dept}</span>
          </div>
        </div>
        <div style={{ textAlign:'right', flexShrink:0 }}>
          <div style={{ fontSize:18, fontWeight:800, color: free ? 'var(--green)' : 'var(--accent)' }}>
            {free ? 'Free' : `${cost} pts`}
          </div>
        </div>
      </div>

      {listing.personality && (
        <div style={{ fontSize:11, color:'var(--muted)', marginBottom:10, lineHeight:1.5,
          borderLeft:'2px solid var(--border)', paddingLeft:8 }}>
          {listing.personality.substring(0,120)}…
        </div>
      )}

      {!open ? (
        <button className="btn btn-primary" style={{ width:'100%' }} onClick={() => setOpen(true)}>
          🛒 Acquire Agent
        </button>
      ) : (
        <div style={{ borderTop:'1px solid var(--border)', paddingTop:10 }}>
          <div style={{ display:'flex', gap:8, alignItems:'center' }}>
            <select className="form-control" style={{ flex:1 }} value={buyDept} onChange={e => setBuyDept(e.target.value)}>
              {DEPT_IDS.map(d => <option key={d} value={d}>{d} ({balances[d]||0} pts)</option>)}
            </select>
            <button className="btn btn-success" disabled={isBuying || (cost > 0 && bal < cost)}
              onClick={() => onBuy(listing.id, buyDept)}>
              {isBuying ? <Spinner /> : '✓ Buy'}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setOpen(false)}>✕</button>
          </div>
          {cost > 0 && bal < cost && (
            <div style={{ fontSize:11, color:'var(--red)', marginTop:4 }}>
              ⚠ {buyDept} has {bal} pts, need {cost}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Extension card ────────────────────────────────────────────────────────────
function ExtCard({ listing, balances, onBuy, isBuying }) {
  const [buyDept,  setBuyDept]  = useState('HF')
  const [buyType,  setBuyType]  = useState('usage')
  const [open,     setOpen]     = useState(false)
  const cost = buyType === 'ownership' ? (listing.price_ownership||0) : (listing.price_usage||0)
  const bal  = balances[buyDept] || 0
  const now  = new Date().toISOString()
  const flash = listing.flash_expires && listing.flash_expires > now

  return (
    <div className="card" style={{ border: flash ? '1px solid var(--orange)' : undefined }}>
      {flash && (
        <div style={{ fontSize:10, fontWeight:800, color:'var(--orange)', marginBottom:8 }}>
          ⚡ FLASH SALE — expires {listing.flash_expires?.substring(0,16).replace('T',' ')}
        </div>
      )}
      <div style={{ display:'flex', gap:10, justifyContent:'space-between', marginBottom:8 }}>
        <div>
          <div style={{ fontSize:14, fontWeight:700 }}>{listing.ext_name}</div>
          <div style={{ fontSize:11, color:'var(--muted)' }}>
            Owner: <span className="dept-tag" style={{ background:COLORS[listing.owner_dept]||'#607D8B', fontSize:9 }}>{listing.owner_dept}</span>
            · {listing.buyer_count} buyer{listing.buyer_count !== 1 ? 's' : ''}
          </div>
        </div>
        <div style={{ textAlign:'right', flexShrink:0 }}>
          <div style={{ fontSize:11, color:'var(--muted)' }}>Usage: <strong style={{ color:'var(--accent)' }}>{listing.price_usage} pts</strong></div>
          <div style={{ fontSize:11, color:'var(--muted)' }}>Ownership: <strong style={{ color:'var(--orange)' }}>{listing.price_ownership} pts</strong></div>
        </div>
      </div>
      {listing.description && <div style={{ fontSize:12, color:'var(--muted)', marginBottom:10 }}>{listing.description}</div>}

      {!open ? (
        <button className="btn btn-primary" style={{ width:'100%' }} onClick={() => setOpen(true)}>
          🛒 Purchase Access
        </button>
      ) : (
        <div style={{ borderTop:'1px solid var(--border)', paddingTop:10 }}>
          <div style={{ display:'flex', gap:6, marginBottom:8 }}>
            {['usage','ownership'].map(t => (
              <button key={t} className={`btn btn-sm ${buyType===t?'btn-primary':'btn-outline'}`}
                onClick={() => setBuyType(t)}>
                {t === 'usage' ? '🔑 Usage rights' : '👑 Ownership'} ({t==='usage'?listing.price_usage:listing.price_ownership} pts)
              </button>
            ))}
          </div>
          <div style={{ display:'flex', gap:8, alignItems:'center' }}>
            <select className="form-control" style={{ flex:1 }} value={buyDept} onChange={e => setBuyDept(e.target.value)}>
              {DEPT_IDS.map(d => <option key={d} value={d}>{d} ({balances[d]||0} pts)</option>)}
            </select>
            <button className="btn btn-success" disabled={isBuying || bal < cost}
              onClick={() => onBuy(listing.id, buyDept, buyType)}>
              {isBuying ? <Spinner /> : '✓ Buy'}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setOpen(false)}>✕</button>
          </div>
          {bal < cost && <div style={{ fontSize:11, color:'var(--red)', marginTop:4 }}>Need {cost} pts, have {bal}</div>}
        </div>
      )}
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function MarketplacePage() {
  const { toast } = useApp()
  const [tab,       setTab]      = useState('agents')
  const [agents,    setAgents]   = useState([])
  const [exts,      setExts]     = useState([])
  const [balances,  setBalances] = useState({})
  const [loading,   setLoading]  = useState(true)
  const [buying,    setBuying]   = useState(null)

  // List agent form
  const [showListAgent, setShowListAgent] = useState(false)
  const [allAgents,     setAllAgents]     = useState([])
  const [selAgent,      setSelAgent]      = useState('')
  const [listPrice,     setListPrice]     = useState(0)
  const [listSeller,    setListSeller]    = useState('founder')

  // List extension form
  const [showListExt,   setShowListExt]   = useState(false)
  const [extId,         setExtId]         = useState('')
  const [extName,       setExtName]       = useState('')
  const [extOwner,      setExtOwner]      = useState('HF')
  const [extPriceOwn,   setExtPriceOwn]   = useState(100)
  const [extPriceUse,   setExtPriceUse]   = useState(20)
  const [extDesc,       setExtDesc]       = useState('')
  const [extFlash,      setExtFlash]      = useState(0)

  const load = useCallback(async () => {
    setLoading(true)
    const [a, e, b, aa] = await Promise.all([
      getMarketAgents().catch(() => []),
      getMarketExtensions().catch(() => []),
      getEconomyBalances().catch(() => ({})),
      getAgents({ status:'active' }).catch(() => []),
    ])
    setAgents(a); setExts(e); setBalances(b)
    setAllAgents(aa.filter(ag => ag.status === 'active'))
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const buyAgent = async (lid, dept) => {
    setBuying(lid)
    const r = await buyMarketAgent(lid, { buyer_dept: dept }).catch(e => ({ error: e.message }))
    if (r.error) toast(r.error, 'error')
    else toast(`Agent acquired by ${dept} ✓`)
    setBuying(null); load()
  }

  const buyExt = async (lid, dept, type) => {
    setBuying(lid)
    const r = await buyMarketExtension(lid, { buyer_dept: dept, buy_type: type }).catch(e => ({ error: e.message }))
    if (r.error) toast(r.error, 'error')
    else toast(`Extension ${type} rights acquired ✓`)
    setBuying(null); load()
  }

  const doListAgent = async () => {
    if (!selAgent) return
    await listAgentForSale({ agent_id: selAgent, seller_dept: listSeller, price: listPrice })
    toast('Agent listed ✓'); setShowListAgent(false); load()
  }

  const doListExt = async () => {
    await listExtForSale({
      ext_id: extId, ext_name: extName, owner_dept: extOwner,
      price_ownership: extPriceOwn, price_usage: extPriceUse,
      description: extDesc, flash_hours: extFlash,
    })
    toast('Extension listed ✓'); setShowListExt(false); load()
  }

  return (
    <div>
      <div className="page-header" style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', flexWrap:'wrap', gap:12 }}>
        <div>
          <h2>🏪 Marketplace</h2>
          <p>Hire agents, acquire extension rights — buy and sell with department points</p>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-outline" onClick={() => setShowListAgent(true)}>+ List Agent</button>
          <button className="btn btn-outline" onClick={() => setShowListExt(true)}>+ List Extension</button>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${tab==='agents'?' active':''}`} onClick={() => setTab('agents')}>
          🤖 Agents {agents.length > 0 && <span className="badge" style={{ marginLeft:4, background:'var(--accent)' }}>{agents.length}</span>}
        </button>
        <button className={`tab${tab==='extensions'?' active':''}`} onClick={() => setTab('extensions')}>
          🧩 Extensions {exts.length > 0 && <span className="badge" style={{ marginLeft:4, background:'var(--accent)' }}>{exts.length}</span>}
        </button>
      </div>

      {loading ? <div className="empty"><Spinner /></div> : (
        tab === 'agents' ? (
          agents.length === 0 ? (
            <div className="empty">No agents listed for sale.<br/>
              <button className="btn btn-outline" style={{ marginTop:12 }} onClick={() => setShowListAgent(true)}>
                + List an Agent
              </button>
            </div>
          ) : (
            <div style={{ display:'grid', gap:16, gridTemplateColumns:'repeat(auto-fill, minmax(320px, 1fr))' }}>
              {agents.map(a => (
                <AgentCard key={a.id} listing={a} balances={balances}
                  onBuy={buyAgent} isBuying={buying === a.id} />
              ))}
            </div>
          )
        ) : (
          exts.length === 0 ? (
            <div className="empty">No extensions listed.<br/>
              <button className="btn btn-outline" style={{ marginTop:12 }} onClick={() => setShowListExt(true)}>
                + List an Extension
              </button>
            </div>
          ) : (
            <div style={{ display:'grid', gap:16, gridTemplateColumns:'repeat(auto-fill, minmax(320px, 1fr))' }}>
              {exts.map(e => (
                <ExtCard key={e.id} listing={e} balances={balances}
                  onBuy={buyExt} isBuying={buying === e.id} />
              ))}
            </div>
          )
        )
      )}

      {/* List Agent Modal */}
      <Modal open={showListAgent} onClose={() => setShowListAgent(false)}>
        <h3 style={{ marginBottom:16 }}>+ List Agent for Sale</h3>
        <div className="form-group">
          <label className="form-label">Agent</label>
          <select className="form-control" value={selAgent} onChange={e => setSelAgent(e.target.value)}>
            <option value="">— select agent —</option>
            {allAgents.map(a => <option key={a.id} value={a.id}>{a.name} ({a.dept_id})</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Seller Dept / Founder</label>
          <select className="form-control" value={listSeller} onChange={e => setListSeller(e.target.value)}>
            <option value="founder">Founder (you)</option>
            {DEPT_IDS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Price (pts) — 0 = free</label>
          <input type="number" className="form-control" min={0} value={listPrice} onChange={e => setListPrice(Number(e.target.value))} />
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-primary" onClick={doListAgent} disabled={!selAgent}>List Agent</button>
          <button className="btn btn-ghost" onClick={() => setShowListAgent(false)}>Cancel</button>
        </div>
      </Modal>

      {/* List Extension Modal */}
      <Modal open={showListExt} onClose={() => setShowListExt(false)}>
        <h3 style={{ marginBottom:16 }}>+ List Extension</h3>
        <div className="form-row form-row-2">
          <div className="form-group">
            <label className="form-label">Extension ID</label>
            <input className="form-control" placeholder="web_search_tool" value={extId} onChange={e => setExtId(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Display Name</label>
            <input className="form-control" placeholder="Web Search Tool" value={extName} onChange={e => setExtName(e.target.value)} />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Owner Department</label>
          <select className="form-control" value={extOwner} onChange={e => setExtOwner(e.target.value)}>
            {DEPT_IDS.map(d => <option key={d} value={d}>{DEPT_NAMES[d]}</option>)}
          </select>
        </div>
        <div className="form-row form-row-2">
          <div className="form-group">
            <label className="form-label">Usage Rights Price (pts)</label>
            <input type="number" className="form-control" min={0} value={extPriceUse} onChange={e => setExtPriceUse(Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label className="form-label">Ownership Price (pts)</label>
            <input type="number" className="form-control" min={0} value={extPriceOwn} onChange={e => setExtPriceOwn(Number(e.target.value))} />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Flash Sale Hours (0 = no flash)</label>
          <input type="number" className="form-control" min={0} value={extFlash} onChange={e => setExtFlash(Number(e.target.value))} />
        </div>
        <div className="form-group">
          <label className="form-label">Description</label>
          <textarea className="form-control" rows={3} value={extDesc} onChange={e => setExtDesc(e.target.value)} />
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-primary" onClick={doListExt} disabled={!extId||!extName}>List Extension</button>
          <button className="btn btn-ghost" onClick={() => setShowListExt(false)}>Cancel</button>
        </div>
      </Modal>
    </div>
  )
}
