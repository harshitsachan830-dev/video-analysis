import { useState, useRef, useEffect, useCallback } from 'react'
import './index.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const GEMINI_ENDPOINTS = new Set([
  '/chat', '/summary', '/timestamp-query', '/generate-notes', '/generate-mcqs',
  '/extract-mnemonics', '/generate-interview-questions', '/extract-visuals',
  '/chat-with-memory', '/check-hallucination', '/generate-revision-notes',
])

/* ─── SVG ICONS ─────────────────────────────────────────── */
const IcHome     = () => <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
const IcVideo    = () => <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>
const IcChat     = () => <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
const IcNotes    = () => <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="7" y1="8" x2="17" y2="8"/><line x1="7" y1="12" x2="14" y2="12"/><line x1="7" y1="16" x2="11" y2="16"/></svg>
const IcQuiz     = () => <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9.5 9a2.5 2.5 0 015 0c0 1.5-2.5 2-2.5 3.5"/><circle cx="12" cy="17" r=".5" fill="currentColor"/></svg>
const IcFlash    = () => <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
const IcMind     = () => <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><circle cx="4" cy="6" r="2"/><circle cx="20" cy="6" r="2"/><circle cx="4" cy="18" r="2"/><circle cx="20" cy="18" r="2"/><line x1="9.4" y1="10.4" x2="5.6" y2="7.6"/><line x1="14.6" y1="10.4" x2="18.4" y2="7.6"/><line x1="9.4" y1="13.6" x2="5.6" y2="16.4"/><line x1="14.6" y1="13.6" x2="18.4" y2="16.4"/></svg>
const IcBookmark = () => <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/></svg>
const IcBar      = () => <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
const IcSearch   = () => <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
const IcSun      = () => <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
const IcBell     = () => <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>
const IcLink     = () => <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>
const IcSpark    = () => <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M12 2l2.09 6.26L20 10l-5.91 1.74L12 18l-2.09-6.26L4 10l5.91-1.74z"/></svg>
const IcPlayLogo = () => <svg viewBox="0 0 24 24" width="14" height="16" fill="white"><path d="M5 3l14 9-14 9V3z"/></svg>
const IcArrow    = () => <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>

/* ─── NAV ITEMS ─────────────────────────────────────────── */
const NAV_ITEMS = [
  { id:'dashboard',  Icon:IcHome,     label:'Dashboard' },
  { id:'videos',     Icon:IcVideo,    label:'My Videos' },
  { id:'chat',       Icon:IcChat,     label:'AI Chat' },
  { id:'notes',      Icon:IcNotes,    label:'Notes & Summaries' },
  { id:'quizzes',    Icon:IcQuiz,     label:'Quizzes' },
  { id:'flashcards', Icon:IcFlash,    label:'Flashcards' },
  { id:'mindmaps',   Icon:IcMind,     label:'Mind Maps' },
  { id:'bookmarks',  Icon:IcBookmark, label:'Bookmarks' },
  { id:'analytics',  Icon:IcBar,      label:'Analytics' },
]

/* ─── FEATURE CARDS ─────────────────────────────────────── */
const FEATURE_CARDS = [
  {
    id:'summary', tab:'chat',
    iconBg:'linear-gradient(135deg,#6B1FE0,#9A50F5)',
    color:'#7028E4',
    icon:<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="7" x2="16" y2="7"/><line x1="8" y1="11" x2="16" y2="11"/><line x1="8" y1="15" x2="13" y2="15"/></svg>,
    title:'Full Summary', desc:'Get complete video summary',
  },
  {
    id:'timestamp', tab:'timestamp',
    iconBg:'linear-gradient(135deg,#B07000,#EC9000)',
    color:'#C07800',
    icon:<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>,
    title:'Ask by Timestamp', desc:'Ask what happened at any time',
  },
  {
    id:'concepts', tab:'mnemonics',
    iconBg:'linear-gradient(135deg,#0880B8,#26C2EA)',
    color:'#0E90C4',
    icon:<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round"><path d="M12 2a7 7 0 015 11.9V20a1 1 0 01-1 1H8a1 1 0 01-1-1v-6.1A7 7 0 0112 2z"/><line x1="9" y1="21" x2="15" y2="21"/></svg>,
    title:'Key Concepts', desc:'Extract formulas, mnemonics & more',
  },
  {
    id:'quiz', tab:'mcq',
    iconBg:'linear-gradient(135deg,#A80E50,#DE306E)',
    color:'#B81055',
    icon:<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9.5 9.5a2.5 2.5 0 014.7 1.2c0 1.5-2.2 2-2.2 3.3"/><circle cx="12" cy="17.5" r=".6" fill="white"/></svg>,
    title:'Generate Quiz', desc:'MCQs, interviews & practice questions',
  },
  {
    id:'notes', tab:'notes',
    iconBg:'linear-gradient(135deg,#027A52,#08C470)',
    color:'#049060',
    icon:<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="7" y1="8" x2="17" y2="8"/><line x1="7" y1="12" x2="17" y2="12"/><polyline points="7 16 9 18 13 14"/></svg>,
    title:'Smart Notes', desc:'Chapter-wise revision notes',
  },
]

/* ─── DEMO RECENT VIDEOS ────────────────────────────────── */
const DEMO_VIDEOS = [
  { id:'d1', title:'System Design Course',  channel:'CodeHelp',         duration:'7:42:31', ago:'2 days ago',   bg:'linear-gradient(160deg,#0C052A,#1A0E50)', txt:'SYSTEM\nDESIGN' },
  { id:'d2', title:'Python Full Course',    channel:'Traversy Media',   duration:'4:26:08', ago:'5 days ago',   bg:'linear-gradient(160deg,#081525,#0D2448)', txt:'PYTHON\nFULL COURSE' },
  { id:'d3', title:'Full Linear Algebra',   channel:'Dr. Trefor Bazett',duration:'2:15:03', ago:'1 week ago',   bg:'linear-gradient(160deg,#051C32,#0B2C50)', txt:'LINEAR\nALGEBRA' },
  { id:'d4', title:'AI For Everyone',       channel:'Andrew Ng',        duration:'1:35:20', ago:'1 week ago',   bg:'linear-gradient(160deg,#150825,#251040)', txt:'AI FOR\nEVERYONE' },
]

/* ─── TABS (existing) ───────────────────────────────────── */
const TABS = [
  { id:'chat',      icon:'💬', label:'Chat' },
  { id:'visuals',   icon:'🖼️', label:'Visuals' },
  { id:'timestamp', icon:'🕐', label:'Timestamp' },
  { id:'notes',     icon:'📝', label:'Notes' },
  { id:'mcq',       icon:'🧠', label:'Quiz' },
  { id:'mnemonics', icon:'🔑', label:'Mnemonics' },
  { id:'interview', icon:'💼', label:'Interview' },
  { id:'analytics', icon:'📈', label:'Analytics' },
  { id:'graph',     icon:'🌐', label:'Graph' },
]

/* ─── CIRCLE PROGRESS ───────────────────────────────────── */
function CircleProgress({ pct = 65, size = 72, sw = 7 }) {
  const r    = (size - sw) / 2
  const circ = 2 * Math.PI * r
  return (
    <svg width={size} height={size} style={{ transform:'rotate(-90deg)', display:'block', flexShrink:0 }}>
      <defs>
        <linearGradient id="cpg" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#7028E4"/>
          <stop offset="100%" stopColor="#26C2EA"/>
        </linearGradient>
      </defs>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#1C1C38" strokeWidth={sw}/>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="url(#cpg)" strokeWidth={sw}
        strokeDasharray={`${circ*pct/100} ${circ*(1-pct/100)}`} strokeLinecap="round"/>
    </svg>
  )
}

/* ─── STREAK RING ───────────────────────────────────────── */
function StreakRing({ pct = 0.72, size = 52, sw = 5 }) {
  const r    = (size - sw) / 2
  const circ = 2 * Math.PI * r
  return (
    <svg width={size} height={size} style={{ transform:'rotate(-90deg)', display:'block', flexShrink:0 }}>
      <defs>
        <linearGradient id="srg" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#FF8C00"/>
          <stop offset="100%" stopColor="#FF4500"/>
        </linearGradient>
      </defs>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#1C1C38" strokeWidth={sw}/>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="url(#srg)" strokeWidth={sw}
        strokeDasharray={`${circ*pct} ${circ*(1-pct)}`} strokeLinecap="round"/>
    </svg>
  )
}

/* ─── MARKDOWN RENDERER ─────────────────────────────────── */
function MarkdownText({ text }) {
  if (!text) return null
  const lines = text.split('\n')
  return (
    <div className="markdown-body">
      {lines.map((line, i) => {
        if (line.startsWith('## '))  return <h2 key={i}>{ri(line.slice(3))}</h2>
        if (line.startsWith('### ')) return <h3 key={i}>{ri(line.slice(4))}</h3>
        if (line.startsWith('# '))  return <h1 key={i}>{ri(line.slice(2))}</h1>
        if (line.startsWith('- ') || line.startsWith('• '))
          return <li key={i}>{ri(line.slice(2))}</li>
        if (/^\d+\.\s/.test(line))
          return <li key={i} className="numbered">{ri(line.replace(/^\d+\.\s/,''))}</li>
        if (line.trim() === '---') return <hr key={i}/>
        if (line.trim() === '')   return <br key={i}/>
        return <p key={i}>{ri(line)}</p>
      })}
    </div>
  )
}
function ri(t) {
  return t.split(/\*\*(.*?)\*\*/g).map((p,j) => j%2===1 ? <strong key={j}>{p}</strong> : p)
}

/* ════════════════════════════════════════════════════════════
   MAIN APP
   ════════════════════════════════════════════════════════════ */
function App() {

  /* ── Existing state ── */
  const [url,             setUrl]             = useState('')
  const [videoId,         setVideoId]         = useState(null)
  const [chunkCount,      setChunkCount]      = useState(0)
  const [loadStatus,      setLoadStatus]      = useState(null)
  const [loadError,       setLoadError]       = useState('')
  const [activeTab,       setActiveTab]       = useState('chat')
  const [messages,        setMessages]        = useState([])
  const [chatInput,       setChatInput]       = useState('')
  const [isThinking,      setIsThinking]      = useState(false)
  const messagesEndRef = useRef(null)
  const [tsInput,         setTsInput]         = useState('')
  const [tsResult,        setTsResult]        = useState(null)
  const [tsLoading,       setTsLoading]       = useState(false)
  const [notes,           setNotes]           = useState('')
  const [notesLoading,    setNotesLoading]    = useState(false)
  const [mcqs,            setMcqs]            = useState([])
  const [mcqLoading,      setMcqLoading]      = useState(false)
  const [selectedAnswers, setSelectedAnswers] = useState({})
  const [mnemonics,       setMnemonics]       = useState('')
  const [mnemonicsLoading,setMnemonicsLoading]= useState(false)
  const [interview,       setInterview]       = useState('')
  const [interviewLoading,setInterviewLoading]= useState(false)
  const [summary,         setSummary]         = useState('')
  const [summaryLoading,  setSummaryLoading]  = useState(false)
  const [visualChunks,    setVisualChunks]    = useState([])
  const [visualError,     setVisualError]     = useState('')
  const [visualsLoading,  setVisualsLoading]  = useState(false)
  const [dashboard,       setDashboard]       = useState(null)
  const [profile,         setProfile]         = useState(null)
  const [analyticsLoading,setAnalyticsLoading]= useState(false)
  const [graphData,       setGraphData]       = useState(null)
  const [graphLoading,    setGraphLoading]    = useState(false)
  const [factCheckResults,setFactCheckResults]= useState({})
  const [savedVideos,     setSavedVideos]     = useState([])
  const [deletingId,      setDeletingId]      = useState(null)
  const [geminiApiKey,    setGeminiApiKey]    = useState('')
  const [geminiKeyDraft,  setGeminiKeyDraft]  = useState('')
  const [keySettingsOpen, setKeySettingsOpen] = useState(false)

  /* ── New UI state ── */
  const [activeNav,    setActiveNav]    = useState('dashboard')
  const [quickAsk,     setQuickAsk]     = useState('')

  const apiFetch = useCallback((input, options = {}) => {
    const headers = new Headers(options.headers)
    const pathname = new URL(input, API).pathname
    if (geminiApiKey.trim() && GEMINI_ENDPOINTS.has(pathname)) {
      headers.set('X-Gemini-API-Key', geminiApiKey.trim())
    }
    return fetch(input, { ...options, headers })
  }, [geminiApiKey])

  const openKeySettings = () => {
    setGeminiKeyDraft(geminiApiKey)
    setKeySettingsOpen(true)
  }

  /* ── Auto-scroll ── */
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior:'smooth' }) }, [messages, isThinking])

  /* ── Fetch saved videos ── */
  const fetchSavedVideos = useCallback(async () => {
    try { const r = await apiFetch(`${API}/videos`); const d = await r.json(); setSavedVideos(d.videos || []) }
    catch { setSavedVideos([]) }
  }, [apiFetch])
  useEffect(() => { fetchSavedVideos() }, [fetchSavedVideos])

  /* ── HANDLERS (all existing, unchanged) ── */
  const handleLoadSaved = (vid) => {
    setVideoId(vid.video_id); setChunkCount(vid.total_chunks); setLoadStatus('loaded'); setUrl('')
    setMessages([{ role:'ai', content:`✅ Loaded **${vid.video_id}** from disk!\n\n💾 **${vid.total_chunks} chunks** already indexed.\n\nSwitch tabs to use all features.`, sources:[] }])
    setNotes(''); setMcqs([]); setMnemonics(''); setInterview(''); setTsResult(null); setSummary(''); setSelectedAnswers({}); setVisualChunks([]); setVisualError(''); setFactCheckResults({})
    setActiveTab('chat'); setActiveNav('chat')
  }

  const handleDeleteVideo = async (vid_id, e) => {
    e.stopPropagation()
    if (!window.confirm(`Delete "${vid_id}" from disk?`)) return
    setDeletingId(vid_id)
    try {
      await apiFetch(`${API}/delete-video/${vid_id}`, { method:'DELETE' })
      if (videoId === vid_id) { setVideoId(null); setLoadStatus(null); setMessages([]); setActiveNav('dashboard') }
      await fetchSavedVideos()
    } catch(err) { console.error(err) }
    finally { setDeletingId(null) }
  }

  const handleLoadVideo = async () => {
    if (!url.trim()) return
    setLoadStatus('loading'); setLoadError(''); setVideoId(null); setMessages([]); setSummary(''); setNotes(''); setMcqs([]); setMnemonics(''); setInterview(''); setTsResult(null); setSelectedAnswers({}); setVisualChunks([]); setVisualError(''); setFactCheckResults({})
    try {
      const res  = await apiFetch(`${API}/load-video`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ url:url.trim() }) })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to load video')
      setVideoId(data.video_id); setChunkCount(data.chunk_count); setLoadStatus('loaded')
      setMessages([{ role:'ai', content:`✅ Video indexed! **${data.chunk_count} chunks** ready.\n\nClick a feature card or use the tabs to explore.`, sources:[] }])
      apiFetch(`${API}/analytics/session/start`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ video_id:data.video_id }) }).catch(console.error)
      fetchSavedVideos()
    } catch(err) { setLoadStatus('error'); setLoadError(err.message) }
  }

  const handleSendMessage = async () => {
    if (!chatInput.trim() || !videoId || isThinking) return
    const question = chatInput.trim(); setChatInput('')
    setMessages(prev => [...prev, { role:'user', content:question, sources:[] }]); setIsThinking(true)
    try {
      const res  = await apiFetch(`${API}/chat-with-memory`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ video_id:videoId, question }) })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed')
      setMessages(prev => [...prev, { role:'ai', content:data.answer, sources:data.sources || [], id:Date.now() }])
    } catch(err) { setMessages(prev => [...prev, { role:'ai', content:`❌ Error: ${err.message}`, sources:[] }]) }
    finally { setIsThinking(false) }
  }

  const handleClearHistory = async () => {
    if (!videoId) return
    try { await apiFetch(`${API}/chat-history/${videoId}`, { method:'DELETE' }); setMessages([{ role:'ai', content:'🧹 Chat history cleared!', sources:[] }]) }
    catch(err) { console.error(err) }
  }

  const handleFactCheck = async (answerText, msgId) => {
    if (factCheckResults[msgId]) return
    setFactCheckResults(prev => ({ ...prev, [msgId]:{ loading:true } }))
    try {
      const res  = await apiFetch(`${API}/check-hallucination`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ video_id:videoId, answer:answerText }) })
      const data = await res.json()
      setFactCheckResults(prev => ({ ...prev, [msgId]:{ loading:false, data } }))
    } catch { setFactCheckResults(prev => ({ ...prev, [msgId]:{ loading:false, error:true } })) }
  }

  const handleSummary = async () => {
    if (!videoId || summaryLoading) return
    setSummaryLoading(true); setSummary('')
    try { const res = await apiFetch(`${API}/summary`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ video_id:videoId }) }); const data = await res.json(); if (!res.ok) throw new Error(data.detail); setSummary(data.summary) }
    catch(err) { setSummary(`❌ Error: ${err.message}`) }
    finally { setSummaryLoading(false) }
  }

  const handleTimestampQuery = async () => {
    if (!tsInput.trim() || !videoId || tsLoading) return
    setTsLoading(true); setTsResult(null)
    try { const res = await apiFetch(`${API}/timestamp-query`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ video_id:videoId, timestamp:tsInput.trim() }) }); const data = await res.json(); if (!res.ok) throw new Error(data.detail); setTsResult(data) }
    catch(err) { setTsResult({ error:err.message }) }
    finally { setTsLoading(false) }
  }

  const handleNotes = useCallback(async () => {
    if (!videoId || notesLoading) return
    setNotesLoading(true); setNotes('')
    try { const res = await apiFetch(`${API}/generate-notes`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ video_id:videoId }) }); const data = await res.json(); if (!res.ok) throw new Error(data.detail); setNotes(data.notes) }
    catch(err) { setNotes(`❌ Error: ${err.message}`) }
    finally { setNotesLoading(false) }
  }, [apiFetch, videoId, notesLoading])

  const handleMCQs = useCallback(async () => {
    if (!videoId || mcqLoading) return
    setMcqLoading(true); setMcqs([]); setSelectedAnswers({})
    try { const res = await apiFetch(`${API}/generate-mcqs`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ video_id:videoId, count:5 }) }); const data = await res.json(); if (!res.ok) throw new Error(data.detail); setMcqs(data.mcqs || []) }
    catch(err) { setMcqs([{ question:`❌ Error: ${err.message}`, options:[], answer:'', explanation:'', timestamp:'' }]) }
    finally { setMcqLoading(false) }
  }, [apiFetch, videoId, mcqLoading])

  const handleSelectAnswer = (qi, letter, q) => {
    setSelectedAnswers(prev => ({ ...prev, [qi]:letter }))
    const isCorrect = letter === q.answer
    apiFetch(`${API}/analytics/log-mcq`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ video_id:videoId, question:q.question, selected:letter, correct_answer:q.answer, is_correct:isCorrect, topic_hint:q.explanation }) }).catch(console.error)
  }

  const handleMnemonics = useCallback(async () => {
    if (!videoId || mnemonicsLoading) return
    setMnemonicsLoading(true); setMnemonics('')
    try { const res = await apiFetch(`${API}/extract-mnemonics`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ video_id:videoId }) }); const data = await res.json(); if (!res.ok) throw new Error(data.detail); setMnemonics(data.mnemonics) }
    catch(err) { setMnemonics(`❌ Error: ${err.message}`) }
    finally { setMnemonicsLoading(false) }
  }, [apiFetch, videoId, mnemonicsLoading])

  const handleInterview = useCallback(async () => {
    if (!videoId || interviewLoading) return
    setInterviewLoading(true); setInterview('')
    try { const res = await apiFetch(`${API}/generate-interview-questions`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ video_id:videoId }) }); const data = await res.json(); if (!res.ok) throw new Error(data.detail); setInterview(data.questions) }
    catch(err) { setInterview(`❌ Error: ${err.message}`) }
    finally { setInterviewLoading(false) }
  }, [apiFetch, videoId, interviewLoading])

  const handleFetchVisuals = async () => {
    setVisualsLoading(true)
    setVisualError('')
    try {
      const res = await apiFetch(`${API}/visual-context/${videoId}`)
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to load visual insights')
      if (data.visual_chunks) setVisualChunks(data.visual_chunks)
    } catch(err) { setVisualError(err.message) }
    finally { setVisualsLoading(false) }
  }
  const handleExtractVisuals = async () => {
    setVisualsLoading(true)
    setVisualError('')
    try {
      const res = await apiFetch(`${API}/extract-visuals`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ video_id:videoId }) })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Visual extraction failed')
      if (data.status === 'failed') throw new Error(data.error || 'Visual extraction failed')
      setVisualChunks(data.visual_chunks || [])
    } catch(err) { setVisualError(err.message) }
    finally { setVisualsLoading(false) }
  }
  const handleFetchAnalytics = async () => {
    setAnalyticsLoading(true)
    try { const [dr,pr] = await Promise.all([apiFetch(`${API}/analytics/dashboard`), apiFetch(`${API}/analytics/profile`)]); setDashboard(await dr.json()); setProfile(await pr.json()) }
    catch { } finally { setAnalyticsLoading(false) }
  }
  const handleFetchGraph = async () => {
    setGraphLoading(true)
    try { const res = await apiFetch(`${API}/knowledge-graph`); setGraphData(await res.json()) }
    catch { } finally { setGraphLoading(false) }
  }

  useEffect(() => {
    if (!videoId) return
    if (activeTab==='notes'     && !notes     && !notesLoading)     handleNotes()
    if (activeTab==='mcq'       && !mcqs.length && !mcqLoading)     handleMCQs()
    if (activeTab==='mnemonics' && !mnemonics && !mnemonicsLoading) handleMnemonics()
    if (activeTab==='interview' && !interview && !interviewLoading) handleInterview()
    if (activeTab==='visuals'   && !visualChunks.length && !visualsLoading) handleFetchVisuals()
    if (activeTab==='analytics' && !dashboard && !analyticsLoading) handleFetchAnalytics()
    if (activeTab==='graph'     && !graphData && !graphLoading)     handleFetchGraph()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, videoId])

  /* ── Navigate to feature tab ── */
  const goFeature = (tab) => {
    if (!videoId) { alert('Please load a YouTube video first!'); return }
    setActiveTab(tab); setActiveNav('chat')
  }

  /* ── Display videos ── */
  const displayVideos = savedVideos.length > 0
    ? savedVideos.map((v, i) => ({
        id:v.video_id, title:v.video_id, channel:'YouTube',
        duration:`${v.total_chunks} chunks`, ago:'recent',
        bg:DEMO_VIDEOS[i % 4].bg, txt:v.video_id.slice(0,12).toUpperCase(),
        realVid:v,
      }))
    : DEMO_VIDEOS

  /* ────────────────────────────────────────────────────────
     RENDER
     ──────────────────────────────────────────────────────── */
  return (
    <>
    <div className="vg-root">

      {/* ══ SIDEBAR ══════════════════════════════════════════ */}
      <aside className="vg-sidebar">

        {/* Logo */}
        <div className="vg-logo">
          <div className="vg-logo-play"><IcPlayLogo/></div>
          <div>
            <div className="vg-logo-name">VideoGPT <span className="vg-pro-tag">Pro</span></div>
            <div className="vg-logo-sub">Understand. Learn. Master.</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="vg-nav">
          {NAV_ITEMS.map(({ id, Icon, label }) => (
            <button key={id}
              className={`vg-nav-item${activeNav===id?' active':''}`}
              onClick={() => setActiveNav(id)}
            >
              <span className="vg-nav-ic"><Icon/></span>
              <span>{label}</span>
            </button>
          ))}
        </nav>

        {/* Bottom cards */}
        <div className="vg-sb-bottom">

          {/* Streak */}
          <div className="vg-sb-card">
            <div className="vg-sb-card-left">
              <div className="vg-sb-label">Learning Streak 🔥</div>
              <div className="vg-streak-row"><span className="vg-streak-num">12</span><span className="vg-streak-days"> days</span></div>
              <div className="vg-sb-sub">Keep going, Harshit!</div>
            </div>
            <div className="vg-streak-ring-wrap">
              <StreakRing pct={0.74}/>
              <div className="vg-streak-ring-ic">🔥</div>
            </div>
          </div>

          {/* Level */}
          <div className="vg-sb-card">
            <span className="vg-level-rocket">🚀</span>
            <div className="vg-level-info">
              <div className="vg-level-name">Level 7</div>
              <div className="vg-level-bar"><div className="vg-level-fill" style={{width:'76.7%'}}/></div>
              <div className="vg-sb-sub">2300 / 3000 XP</div>
            </div>
          </div>

          {/* User */}
          <div className="vg-user-card">
            <div className="vg-user-av">H</div>
            <div className="vg-user-info">
              <div className="vg-user-name">Harshit</div>
              <div className="vg-user-plan">Pro Plan 👑</div>
            </div>
            <span className="vg-chevron">⌄</span>
          </div>
          <button className="vg-key-btn vg-key-btn-sidebar" onClick={openKeySettings}>
            {geminiApiKey ? '🔑 Gemini key added' : '🔑 Add Gemini API key'}
          </button>

        </div>
      </aside>

      {/* ══ MAIN ═════════════════════════════════════════════ */}
      <div className="vg-main">

        {/* Top bar */}
        <div className="vg-topbar">
          <div>
            <div className="vg-welcome">Welcome back, Harshit! 👋</div>
            <h1 className="vg-heading">What do you want to learn today?</h1>
          </div>
          <div className="vg-topbar-right">
            <button className="vg-ic-btn"><IcSearch/></button>
            <button className="vg-ic-btn"><IcSun/></button>
            <button className="vg-ic-btn vg-bell-btn">
              <IcBell/>
              <span className="vg-bell-badge">3</span>
            </button>
            <div className="vg-top-av">H</div>
          </div>
        </div>

        {/* ── DASHBOARD VIEW ─────────────────────────────── */}
        {activeNav === 'dashboard' && (
          <div className="vg-scroll">
            <div className="vg-grid">

              {/* CENTER COLUMN */}
              <div className="vg-center">

                {/* Hero card */}
                <div className="vg-hero">
                  <div className="vg-hero-title">
                    <span className="vg-spark-ic"><IcSpark/></span>
                    Paste a <span className="vg-yt">YouTube</span> link to get started
                  </div>
                  <div className="vg-hero-row">
                    <div className="vg-input-wrap">
                      <span className="vg-input-ic"><IcLink/></span>
                      <input
                        className="vg-url-input"
                        placeholder="https://www.youtube.com/watch?v=..."
                        value={url} onChange={e => setUrl(e.target.value)}
                        onKeyDown={e => e.key==='Enter' && handleLoadVideo()}
                      />
                    </div>
                    <button className="vg-analyze-btn" onClick={handleLoadVideo} disabled={loadStatus==='loading'||!url.trim()}>
                      {loadStatus==='loading'
                        ? <><span className="vg-spin"/>Indexing...</>
                        : <><IcSpark/> Analyze Video</>}
                    </button>
                  </div>
                  {loadStatus==='error'  && <div className="vg-hero-err">❌ {loadError}</div>}
                  {loadStatus==='loaded' && <div className="vg-hero-ok">✅ Video indexed! {chunkCount} chunks ready.</div>}
                  <div className="vg-examples">
                    <span className="vg-ex-label">Try these examples</span>
                    <div className="vg-chips">
                      <button className="vg-chip" onClick={() => setUrl('https://youtu.be/rExSubZero')}>🚀 System Design Course</button>
                      <button className="vg-chip" onClick={() => setUrl('https://youtu.be/PythonCourse')}>🐍 Python Full Course</button>
                      <button className="vg-chip" onClick={() => setUrl('https://youtu.be/MLBasics')}>🧠 Machine Learning Basics</button>
                    </div>
                  </div>
                </div>

                {/* Feature cards */}
                <div className="vg-features">
                  {FEATURE_CARDS.map(f => (
                    <div key={f.id} className="vg-fc" style={{'--fc-c':f.color}} onClick={() => goFeature(f.tab)}>
                      <div className="vg-fc-icon" style={{background:f.iconBg}}>{f.icon}</div>
                      <div className="vg-fc-title">{f.title}</div>
                      <div className="vg-fc-desc">{f.desc}</div>
                      <button className="vg-fc-arrow"><IcArrow/></button>
                    </div>
                  ))}
                </div>

                {/* Recent Videos */}
                <div className="vg-recent-card">
                  <div className="vg-sec-hdr">
                    <span className="vg-sec-title">Recent Videos</span>
                    <button className="vg-view-all">View all</button>
                  </div>
                  <div className="vg-vids-grid">
                    {displayVideos.slice(0,4).map(v => (
                      <div key={v.id} className="vg-vid-card"
                        style={{cursor:v.realVid?'pointer':'default'}}
                        onClick={() => v.realVid && handleLoadSaved(v.realVid)}>
                        <div className="vg-thumb" style={{background:v.bg}}>
                          <span className="vg-thumb-txt">{v.txt}</span>
                          <span className="vg-duration">{v.duration}</span>
                        </div>
                        <div className="vg-vid-meta">
                          <div className="vg-vid-title">{v.title}</div>
                          <div className="vg-vid-ch">by {v.channel}</div>
                          <div className="vg-vid-ago">{v.duration} • {v.ago}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

              </div>{/* end center */}

              {/* RIGHT COLUMN */}
              <div className="vg-right">

                {/* Learning Overview */}
                <div className="vg-rc">
                  <div className="vg-rc-hdr">
                    <span style={{fontSize:'16px'}}>🎯</span>
                    <span className="vg-rc-title">Your Learning Overview</span>
                  </div>
                  <div className="vg-stats">
                    <div className="vg-stat-box">
                      <div className="vg-stat-ic" style={{color:'#9B6FF8'}}>📹</div>
                      <div className="vg-stat-val" style={{color:'#9B6FF8'}}>28</div>
                      <div className="vg-stat-lbl">Videos Analyzed</div>
                    </div>
                    <div className="vg-stat-box">
                      <div className="vg-stat-ic" style={{color:'#FF9A00'}}>💬</div>
                      <div className="vg-stat-val" style={{color:'#FF9A00'}}>156</div>
                      <div className="vg-stat-lbl">Questions Asked</div>
                    </div>
                    <div className="vg-stat-box">
                      <div className="vg-stat-ic" style={{color:'#0FDA77'}}>📈</div>
                      <div className="vg-stat-val" style={{color:'#0FDA77'}}>89%</div>
                      <div className="vg-stat-lbl">Learning Score</div>
                    </div>
                    <div className="vg-stat-box">
                      <div className="vg-stat-ic" style={{color:'#2BC8EF'}}>⏱</div>
                      <div className="vg-stat-val" style={{color:'#2BC8EF'}}>24h</div>
                      <div className="vg-stat-lbl">Time Saved</div>
                    </div>
                  </div>
                </div>

                {/* Continue Learning */}
                <div className="vg-rc">
                  <div className="vg-rc-title-plain">Continue Learning</div>
                  <div className="vg-cl-row">
                    <div className="vg-circle-wrap">
                      <CircleProgress pct={65}/>
                      <div className="vg-circle-lbl">65%</div>
                    </div>
                    <div className="vg-cl-info">
                      <div className="vg-cl-name">System Design Course</div>
                      <div className="vg-cl-bar"><div className="vg-cl-fill"/></div>
                      <div className="vg-cl-sub">7h 42m left</div>
                    </div>
                  </div>
                  <button className="vg-continue-btn" onClick={() => goFeature('chat')}>▶ Continue</button>
                </div>

                {/* Ask Anything */}
                <div className="vg-rc">
                  <div className="vg-rc-hdr">
                    <span style={{fontSize:'15px'}}>🔥</span>
                    <span className="vg-rc-title">Ask Anything</span>
                  </div>
                  <div className="vg-ask-sub">Get instant answers from this video</div>
                  <div className="vg-ask-row">
                    <input className="vg-ask-inp"
                      placeholder="What happened at 6:40?"
                      value={quickAsk} onChange={e => setQuickAsk(e.target.value)}
                      onKeyDown={e => { if(e.key==='Enter'){ setTsInput(quickAsk); setActiveNav('chat'); setActiveTab('timestamp') }}}
                    />
                    <button className="vg-ask-btn" onClick={() => { setTsInput(quickAsk); setActiveNav('chat'); setActiveTab('timestamp') }}>→</button>
                  </div>
                  <div className="vg-ask-chips">
                    <button className="vg-ask-chip" onClick={() => setQuickAsk('System design overview')}>● System design overview</button>
                    <button className="vg-ask-chip" onClick={() => setQuickAsk('Database used?')}>● Database used?</button>
                  </div>
                </div>

                {/* Upgrade to Pro */}
                <div className="vg-rc vg-upgrade">
                  <div className="vg-upgrade-inner">
                    <div>
                      <div className="vg-upgrade-title">👑 Upgrade to Pro</div>
                      <div className="vg-upgrade-desc">Unlock advanced AI models, unlimited uploads, and more.</div>
                      <button className="vg-upgrade-btn">Upgrade Now →</button>
                    </div>
                    <div className="vg-gem">💎</div>
                  </div>
                </div>

              </div>{/* end right */}
            </div>{/* end grid */}

            {/* Bottom Banner */}
            <div className="vg-banner">
              <div className="vg-banner-icon-wrap">💬</div>
              <div className="vg-banner-txt">
                <div className="vg-banner-title">Chat with your video</div>
                <div className="vg-banner-desc">Have a conversation and get answers from your videos</div>
              </div>
              <div className="vg-banner-bubble">💬</div>
              <button className="vg-start-chat" onClick={() => { setActiveNav('chat'); setActiveTab('chat') }}>Start Chat →</button>
            </div>
          </div>
        )}

        {/* ── VIDEO ANALYSIS VIEW (non-dashboard) ─────────── */}
        {activeNav !== 'dashboard' && (
          <div className="vg-analysis">

            {/* Load bar */}
            <div className="vg-load-bar">
              <div className="vg-load-input-wrap">
                <span className="vg-input-ic"><IcLink/></span>
                <input className="vg-url-input vg-load-inp"
                  placeholder="Paste YouTube URL..."
                  value={url} onChange={e => setUrl(e.target.value)}
                  onKeyDown={e => e.key==='Enter' && handleLoadVideo()}
                />
              </div>
              <button className="vg-load-btn" onClick={handleLoadVideo} disabled={loadStatus==='loading'||!url.trim()}>
                {loadStatus==='loading' ? <><span className="vg-spin"/>Indexing...</> : '⚡ Load Video'}
              </button>
              {loadStatus==='loaded' && videoId && (
                <div className="vg-loaded-badge">✅ {videoId} · {chunkCount} chunks</div>
              )}
              {loadStatus==='error' && <div className="vg-err-badge">❌ {loadError}</div>}
            </div>

            {/* Tabs */}
            {videoId && (
              <div className="vg-tabs">
                {TABS.map(t => (
                  <button key={t.id} className={`vg-tab${activeTab===t.id?' active':''}`} onClick={() => setActiveTab(t.id)}>
                    {t.icon} {t.label}
                  </button>
                ))}
              </div>
            )}

            {/* No video */}
            {!videoId && (
              <div className="vg-empty">
                <div className="vg-empty-icon">🎥</div>
                <h2>Chat with any YouTube video</h2>
                <p>Paste a YouTube URL above and click <strong>Load Video</strong></p>
                <div className="vg-feat-pills">{TABS.map(t => <span key={t.id} className="vg-feat-pill">{t.icon} {t.label}</span>)}</div>
              </div>
            )}

            {/* CHAT */}
            {videoId && activeTab==='chat' && (
              <>
                <div className="vg-msgs">
                  <div style={{display:'flex',justifyContent:'center',marginBottom:'1rem'}}>
                    <button className="vg-clear-btn" onClick={handleClearHistory}>🧹 Clear Memory</button>
                  </div>
                  {messages.map((msg,i) => (
                    <div key={i} className={`vg-msg ${msg.role}`}>
                      <div className="vg-bubble">
                        {msg.role==='ai' ? <MarkdownText text={msg.content}/> : msg.content}
                      </div>
                      {msg.role==='ai' && (
                        <div className="vg-msg-actions">
                          {msg.sources?.length>0 && <div className="vg-sources">{msg.sources.map((s,si)=><span key={si} className="vg-src-chip">🕐 {s.timestamp}</span>)}</div>}
                          {msg.id && <button className="vg-fc-btn" onClick={()=>handleFactCheck(msg.content,msg.id)} disabled={factCheckResults[msg.id]?.loading}>{factCheckResults[msg.id]?.loading?'🔍 Checking...':'⚖️ Fact Check'}</button>}
                          {factCheckResults[msg.id]?.data && <span className={`vg-fc-res ${factCheckResults[msg.id].data.is_supported?'fc-ok':'fc-bad'}`}>{factCheckResults[msg.id].data.is_supported?'✅ Supported':'❌ Review'} ({factCheckResults[msg.id].data.confidence_score}%)<div className="vg-fc-tip">{factCheckResults[msg.id].data.reason}</div></span>}
                        </div>
                      )}
                    </div>
                  ))}
                  {isThinking && <div className="vg-msg ai"><div className="vg-typing"><div className="vg-dot"/><div className="vg-dot"/><div className="vg-dot"/></div></div>}
                  <div ref={messagesEndRef}/>
                </div>
                <div className="vg-chat-bar">
                  <textarea className="vg-chat-inp" placeholder="Ask anything about this video... (Enter to send)"
                    value={chatInput} onChange={e=>setChatInput(e.target.value)}
                    onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();handleSendMessage()}}}
                    disabled={isThinking} rows={1}/>
                  <button className="vg-send-btn" onClick={handleSendMessage} disabled={!chatInput.trim()||isThinking}>
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="white"><path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/></svg>
                  </button>
                </div>
              </>
            )}

            {/* TIMESTAMP */}
            {videoId && activeTab==='timestamp' && (
              <div className="vg-tab-content">
                <h2 className="vg-tab-h">🕐 Timestamp Query</h2>
                <p className="vg-tab-sub">Ask what happened at any specific moment</p>
                <div className="vg-ts-row">
                  <input className="vg-ts-inp" placeholder='e.g. "6:40" or "01:30:00"' value={tsInput} onChange={e=>setTsInput(e.target.value)} onKeyDown={e=>e.key==='Enter'&&handleTimestampQuery()}/>
                  <button className="vg-ts-btn" onClick={handleTimestampQuery} disabled={tsLoading||!tsInput.trim()}>{tsLoading?<><span className="vg-spin"/>Searching...</>:'🔍 Query'}</button>
                </div>
                <div className="vg-ts-chips">{['0:30','2:00','5:00','8:30','10:00','15:00'].map(t=><button key={t} className="vg-ts-chip" onClick={()=>setTsInput(t)}>⏱ {t}</button>)}</div>
                {tsResult && !tsResult.error && <div className="vg-result"><div className="vg-result-head">📍 At {tsResult.timestamp}</div><MarkdownText text={tsResult.answer}/><div className="vg-sources">{tsResult.sources?.map((s,i)=><span key={i} className="vg-src-chip">🕐 {s.timestamp}</span>)}</div></div>}
                {tsResult?.error && <div className="vg-err-msg">❌ {tsResult.error}</div>}
              </div>
            )}

            {/* NOTES */}
            {videoId && activeTab==='notes' && (
              <div className="vg-tab-content">
                <h2 className="vg-tab-h">📝 Chapter-wise Notes</h2>
                <p className="vg-tab-sub">Structured study notes from the video</p>
                <button className="vg-action-btn" onClick={handleNotes} disabled={notesLoading}>{notesLoading?<><span className="vg-spin"/>Generating...</>:'🔄 Regenerate Notes'}</button>
                {notesLoading && <div className="vg-loading-msg"><span className="vg-spin"/>Generating notes...</div>}
                {notes && !notesLoading && <div className="vg-result vg-scrollable"><MarkdownText text={notes}/></div>}
              </div>
            )}

            {/* MCQ */}
            {videoId && activeTab==='mcq' && (
              <div className="vg-tab-content">
                <h2 className="vg-tab-h">🧠 MCQ Quiz</h2>
                <p className="vg-tab-sub">Test your knowledge with AI-generated questions</p>
                {mcqLoading && <div className="vg-loading-msg"><span className="vg-spin"/>Generating quiz...</div>}
                {mcqs.length>0 && !mcqLoading && (
                  <div className="vg-mcqs">
                    {mcqs.map((q,qi)=>(
                      <div key={qi} className="vg-mcq">
                        <div className="vg-mcq-q"><span className="vg-mcq-num">Q{qi+1}</span> {q.question}{q.timestamp&&<span className="vg-src-chip" style={{marginLeft:'0.5rem'}}>🕐 {q.timestamp}</span>}</div>
                        <div className="vg-mcq-opts">
                          {q.options?.map((opt,oi)=>{
                            const letter=opt[0],selected=selectedAnswers[qi]===letter,isOk=letter===q.answer,revealed=selectedAnswers[qi]!==undefined
                            return <button key={oi} className={`vg-opt${selected?' sel':''}${revealed&&isOk?' ok':''}${revealed&&selected&&!isOk?' bad':''}`} onClick={()=>!revealed&&handleSelectAnswer(qi,letter,q)}>{opt}</button>
                          })}
                        </div>
                        {selectedAnswers[qi]&&<div className={`vg-exp ${selectedAnswers[qi]===q.answer?'exp-ok':'exp-bad'}`}>{selectedAnswers[qi]===q.answer?'✅ Correct! ':`❌ Wrong. Correct: ${q.answer}. `}{q.explanation}</div>}
                      </div>
                    ))}
                    <button className="vg-action-btn" onClick={handleMCQs} disabled={mcqLoading} style={{marginTop:'1rem'}}>🔄 Regenerate Quiz</button>
                  </div>
                )}
              </div>
            )}

            {/* MNEMONICS */}
            {videoId && activeTab==='mnemonics' && (
              <div className="vg-tab-content">
                <h2 className="vg-tab-h">🔑 Key Concepts & Mnemonics</h2>
                <p className="vg-tab-sub">Formulas, mnemonics, and quick-reference facts</p>
                <button className="vg-action-btn" onClick={handleMnemonics} disabled={mnemonicsLoading}>{mnemonicsLoading?<><span className="vg-spin"/>Extracting...</>:'🔄 Regenerate'}</button>
                {mnemonicsLoading && <div className="vg-loading-msg"><span className="vg-spin"/>Extracting memory aids...</div>}
                {mnemonics && !mnemonicsLoading && <div className="vg-result vg-scrollable"><MarkdownText text={mnemonics}/></div>}
              </div>
            )}

            {/* INTERVIEW */}
            {videoId && activeTab==='interview' && (
              <div className="vg-tab-content">
                <h2 className="vg-tab-h">💼 Interview & Exam Prep</h2>
                <p className="vg-tab-sub">Practice questions from beginner to advanced</p>
                <button className="vg-action-btn" onClick={handleInterview} disabled={interviewLoading}>{interviewLoading?<><span className="vg-spin"/>Generating...</>:'🔄 Regenerate'}</button>
                {interviewLoading && <div className="vg-loading-msg"><span className="vg-spin"/>Generating questions...</div>}
                {interview && !interviewLoading && <div className="vg-result vg-scrollable"><MarkdownText text={interview}/></div>}
              </div>
            )}

            {/* VISUALS */}
            {videoId && activeTab==='visuals' && (
              <div className="vg-tab-content">
                <h2 className="vg-tab-h">🖼️ Visual Insights</h2>
                <p className="vg-tab-sub">Gemini Vision extracts text from slides and whiteboards</p>
                <button className="vg-action-btn" onClick={handleExtractVisuals} disabled={visualsLoading} style={{width:'fit-content'}}>{visualsLoading?<><span className="vg-spin"/>Extracting...</>:'🔍 Run Visual Extraction'}</button>
                {visualsLoading && <div className="vg-loading-msg">Processing frames with Gemini Vision...</div>}
                {visualError && <div className="vg-err-msg">❌ {visualError}</div>}
                {!visualsLoading && visualChunks.length>0 && <div className="vg-visuals-grid">{visualChunks.map((c,i)=><div key={i} className="vg-visual-card"><div className="vg-vis-ts">🕐 {c.timestamp}</div><MarkdownText text={c.analysis}/></div>)}</div>}
              </div>
            )}

            {/* ANALYTICS */}
            {videoId && activeTab==='analytics' && (
              <div className="vg-tab-content">
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:'1rem'}}>
                  <div><h2 className="vg-tab-h">📈 Learning Analytics</h2><p className="vg-tab-sub">Track sessions and quiz performance</p></div>
                  <button className="vg-action-btn" onClick={handleFetchAnalytics} disabled={analyticsLoading} style={{width:'auto'}}>🔄 Refresh</button>
                </div>
                {analyticsLoading && <div className="vg-loading-msg"><span className="vg-spin"/>Loading stats...</div>}
                {!analyticsLoading && dashboard && profile && (
                  <div>
                    <div className="vg-analytics-grid">
                      <div className="vg-a-box"><div className="vg-a-val">{dashboard.total_sessions}</div><div className="vg-a-lbl">Study Sessions</div></div>
                      <div className="vg-a-box"><div className="vg-a-val">{Math.round(dashboard.total_study_minutes)}m</div><div className="vg-a-lbl">Total Time</div></div>
                      <div className="vg-a-box"><div className="vg-a-val">{dashboard.mcq_stats.total_attempted}</div><div className="vg-a-lbl">Questions</div></div>
                      <div className="vg-a-box"><div className="vg-a-val" style={{color:'#0FDA77'}}>{Math.round(dashboard.mcq_stats.overall_accuracy)}%</div><div className="vg-a-lbl">Accuracy</div></div>
                    </div>
                    <div className="vg-result" style={{marginTop:'1rem'}}><h3 style={{color:'#9B6FF8',marginBottom:'0.75rem'}}>🎯 Personalized Profile</h3><p style={{color:'var(--tx2)',lineHeight:1.7}}>{profile.profile.summary}</p>{profile.profile.weak_topics.length>0&&<div style={{marginTop:'1rem'}}><h4 style={{color:'#fca5a5',marginBottom:'0.5rem'}}>⚠️ Needs Revision</h4><ul style={{paddingLeft:'1.5rem',color:'var(--tx2)'}}>{profile.profile.weak_topics.map((t,i)=><li key={i}>{t}</li>)}</ul></div>}</div>
                  </div>
                )}
              </div>
            )}

            {/* GRAPH */}
            {videoId && activeTab==='graph' && (
              <div className="vg-tab-content">
                <h2 className="vg-tab-h">🌐 Knowledge Graph</h2>
                <p className="vg-tab-sub">Concepts connecting multiple videos in your library</p>
                <button className="vg-action-btn" onClick={handleFetchGraph} disabled={graphLoading} style={{width:'fit-content'}}>🔄 Build Concept Map</button>
                {graphLoading && <div className="vg-loading-msg"><span className="vg-spin"/>Analyzing all videos...</div>}
                {!graphLoading && graphData && (
                  <div>
                    <div style={{fontSize:'0.8rem',color:'var(--tx3)',marginBottom:'1rem'}}>Analyzed {graphData.total_videos_analyzed} videos</div>
                    <div className="vg-graph-nodes">{graphData.nodes.map((n,i)=><div key={i} className="vg-graph-node"><div className="vg-gn-concept">{n.concept}</div><div className="vg-gn-meta">×{n.weight} across {n.video_ids.length} videos</div></div>)}</div>
                  </div>
                )}
              </div>
            )}

          </div>
        )}

      </div>{/* end main */}
    </div>{/* end root */}

    {keySettingsOpen && (
      <div className="vg-modal-backdrop" onMouseDown={e => e.target === e.currentTarget && setKeySettingsOpen(false)}>
        <section className="vg-key-modal" role="dialog" aria-modal="true" aria-labelledby="vg-key-title">
          <button className="vg-modal-close" onClick={() => setKeySettingsOpen(false)} aria-label="Close">×</button>
          <div className="vg-key-modal-icon">🔐</div>
          <h2 id="vg-key-title">Use your Gemini API key</h2>
          <p>AI features use your Gemini account and its usage limits. Your key stays in this page’s memory and is sent to this app’s backend for AI requests. The backend uses it with Google Gemini and does not save it.</p>
          <form onSubmit={e => { e.preventDefault(); setGeminiApiKey(geminiKeyDraft.trim()); setKeySettingsOpen(false) }}>
            <label className="vg-key-label" htmlFor="vg-gemini-key">Gemini API key</label>
            <input
              id="vg-gemini-key"
              className="vg-key-input"
              type="password"
              autoComplete="off"
              spellCheck="false"
              placeholder="Paste your Gemini API key"
              value={geminiKeyDraft}
              onChange={e => setGeminiKeyDraft(e.target.value)}
              autoFocus
            />
            <div className="vg-key-actions">
              <button className="vg-key-save" type="submit" disabled={!geminiKeyDraft.trim()}>Save for this session</button>
              {geminiApiKey && <button className="vg-key-remove" type="button" onClick={() => { setGeminiApiKey(''); setGeminiKeyDraft(''); setKeySettingsOpen(false) }}>Remove key</button>}
            </div>
          </form>
          <a className="vg-key-help" href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer">Get a Gemini API key from Google AI Studio ↗</a>
        </section>
      </div>
    )}
    </>
  )
}

export default App
