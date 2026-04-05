import React from 'react'
export default function Spinner({ lg }) {
  return <span className={lg ? 'spinner spinner-lg' : 'spinner'} />
}
