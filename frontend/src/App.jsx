import { useState } from 'react'
import MapComponent from './MapComponent'
import './App.css'

function App() {
  // Mock state for our Top Bar stats
  const [activeIncidentsCount, setActiveIncidentsCount] = useState(0);
  const [availableVolunteersCount, setAvailableVolunteersCount] = useState(50);
  
  // Sidebar states
  const [isLeftOpen, setIsLeftOpen] = useState(true);
  const [isRightOpen, setIsRightOpen] = useState(true);

  return (
    <div className="app-container">
      {/* 1. Top Navigation & Stats Bar */}
      <header className="topbar">
        <div className="topbar-title">DispatchAI</div>
        <div className="topbar-stats">
          <div className="stat-item">
            <span>Active Incidents:</span>
            <span className="stat-value">{activeIncidentsCount}</span>
          </div>
          <div className="stat-item">
            <span>Available Volunteers:</span>
            {/* The 'green' class applies the neon glow for available volunteers */}
            <span className="stat-value green">{availableVolunteersCount}</span>
          </div>
        </div>
      </header>

      {/* 2. Main 3-Column Layout */}
      <div className="main-content">
        
        {/* Left Sidebar: Incident Feed */}
        <aside className={`sidebar-left ${!isLeftOpen ? 'collapsed' : ''}`}>
          <div className="panel-header">
            Incident Feed
            <button className="toggle-btn" onClick={() => setIsLeftOpen(false)} title="Close Sidebar">
              ❮
            </button>
          </div>
          <div className="panel-content">
            <p style={{ opacity: 0.5, fontSize: '0.9rem', textAlign: 'center', marginTop: '2rem' }}>
              Waiting for incoming WhatsApp messages...
            </p>
            {/* Future: We will map() over incidents and render Card components here */}
          </div>
        </aside>

        {!isLeftOpen && (
          <button className="open-sidebar-btn left" onClick={() => setIsLeftOpen(true)}>
            ❯ Incidents
          </button>
        )}

        {/* Center: Live Map Area */}
        <main className="map-container">
          <MapComponent isLeftOpen={isLeftOpen} isRightOpen={isRightOpen} />
        </main>

        {!isRightOpen && (
          <button className="open-sidebar-btn right" onClick={() => setIsRightOpen(true)}>
            AI Reasoning ❮
          </button>
        )}

        {/* Right Sidebar: AI Transparency */}
        <aside className={`sidebar-right ${!isRightOpen ? 'collapsed' : ''}`}>
          <div className="panel-header">
            <button className="toggle-btn" onClick={() => setIsRightOpen(false)} title="Close Sidebar">
              ❯
            </button>
            AI Reasoning
          </div>
          <div className="panel-content">
             <p style={{ opacity: 0.5, fontSize: '0.9rem', textAlign: 'center', marginTop: '2rem', lineHeight: '1.5' }}>
              Qwen LLM thought process will appear here when an incident is processed.
            </p>
            {/* Future: Expandable accordion components will go here */}
          </div>
        </aside>

      </div>
    </div>
  )
}

export default App
