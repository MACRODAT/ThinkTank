import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'

const AppCtx = createContext(null)

const THEMES = ['dark','midnight','forest','amber','rose','ocean','light']

export function AppProvider({ children }) {
  const [toasts,       setToasts]   = useState([])
  const [pendingCount, setPending]  = useState(0)
  const [theme,        setThemeRaw] = useState(() => localStorage.getItem('ctt-theme') || 'dark')

  // Apply theme to <html>
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('ctt-theme', theme)
  }, [theme])

  const setTheme = useCallback((t) => setThemeRaw(t), [])

  const toast = useCallback((msg, type = 'success') => {
    const id = Date.now()
    setToasts(t => [...t, { id, msg, type }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3500)
  }, [])

  return (
    <AppCtx.Provider value={{ toast, toasts, pendingCount, setPending, theme, setTheme, THEMES }}>
      {children}
    </AppCtx.Provider>
  )
}

export const useApp = () => useContext(AppCtx)
