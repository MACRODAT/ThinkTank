import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'

const AppCtx = createContext(null)
const THEMES  = ['dark','midnight','forest','amber','rose','ocean','light']

const FONTS = {
  system:  { label: 'System UI',    value: "'Segoe UI', system-ui, -apple-system, sans-serif" },
  inter:   { label: 'Inter',        value: "'Inter', system-ui, sans-serif" },
  mono:    { label: 'Monospace',    value: "'Cascadia Code', 'Fira Code', 'Consolas', monospace" },
  serif:   { label: 'Serif',        value: "Georgia, 'Times New Roman', serif" },
  roboto:  { label: 'Roboto',       value: "'Roboto', system-ui, sans-serif" },
}

const FONT_SIZES = { small: '13px', medium: '14px', large: '15px', xlarge: '16px' }

export function AppProvider({ children }) {
  const [toasts,       setToasts]      = useState([])
  const [pendingCount, setPending]     = useState(0)
  const [theme,        setThemeRaw]    = useState(() => localStorage.getItem('ctt-theme')    || 'dark')
  const [fontKey,      setFontKeyRaw]  = useState(() => localStorage.getItem('ctt-font')     || 'system')
  const [fontSize,     setFontSzRaw]   = useState(() => localStorage.getItem('ctt-fontsize') || 'medium')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('ctt-theme', theme)
  }, [theme])

  useEffect(() => {
    document.documentElement.style.setProperty('--font-family', FONTS[fontKey]?.value || FONTS.system.value)
    document.body.style.fontFamily = FONTS[fontKey]?.value || FONTS.system.value
    document.body.style.fontSize   = FONT_SIZES[fontSize] || '14px'
    localStorage.setItem('ctt-font',     fontKey)
    localStorage.setItem('ctt-fontsize', fontSize)
  }, [fontKey, fontSize])

  const setTheme   = useCallback((t) => setThemeRaw(t),   [])
  const setFont    = useCallback((f) => setFontKeyRaw(f), [])
  const setFontSize= useCallback((s) => setFontSzRaw(s),  [])

  const toast = useCallback((msg, type = 'success') => {
    const id = Date.now()
    setToasts(t => [...t, { id, msg, type }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3500)
  }, [])

  return (
    <AppCtx.Provider value={{
      toast, toasts, pendingCount, setPending,
      theme, setTheme, THEMES,
      fontKey, setFont, FONTS,
      fontSize, setFontSize, FONT_SIZES,
    }}>
      {children}
    </AppCtx.Provider>
  )
}

export const useApp = () => useContext(AppCtx)
