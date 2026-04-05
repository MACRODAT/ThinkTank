import React, { createContext, useContext, useState, useCallback } from 'react'
const AppCtx = createContext(null)
export function AppProvider({ children }) {
  const [toasts, setToasts]        = useState([])
  const [pendingCount, setPending] = useState(0)
  const toast = useCallback((msg, type = 'success') => {
    const id = Date.now()
    setToasts(t => [...t, { id, msg, type }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3000)
  }, [])
  return (
    <AppCtx.Provider value={{ toast, toasts, pendingCount, setPending }}>
      {children}
    </AppCtx.Provider>
  )
}
export const useApp = () => useContext(AppCtx)
