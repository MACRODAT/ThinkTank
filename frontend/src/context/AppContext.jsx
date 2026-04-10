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
    const fontVal = FONTS[fontKey]?.value || FONTS.system.value
    const sizeVal  = FONT_SIZES[fontSize] || '14px'
    document.documentElement.style.setProperty('--font-family', fontVal)
    document.documentElement.style.setProperty('--font-size-base', sizeVal)
    document.body.style.fontFamily = fontVal
    document.body.style.fontSize   = sizeVal
    // Also patch all existing CSS
    const styleEl = document.getElementById('ctt-font-override') ||
      Object.assign(document.createElement('style'), { id: 'ctt-font-override' })
    styleEl.textContent = `*, body { font-family: ${fontVal} !important; font-size: ${sizeVal}; }`
    if (!document.getElementById('ctt-font-override')) document.head.appendChild(styleEl)
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
