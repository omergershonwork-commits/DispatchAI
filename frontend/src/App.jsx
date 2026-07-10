import { useState } from 'react'
import MapComponent from './MapComponent'
import IncidentCard from './components/IncidentCard'
import AIReasoning from './components/AIReasoning'
import './App.css'

function App() {
  // Mock state for our Top Bar stats
  const [activeIncidentsCount, setActiveIncidentsCount] = useState(0);
  const [availableVolunteersCount, setAvailableVolunteersCount] = useState(50);
  
  // Sidebar states
  const [isLeftOpen, setIsLeftOpen] = useState(true);
  const [isRightOpen, setIsRightOpen] = useState(true);

  // Mock Incidents Data (With coordinates for the map)
  const mockIncidents = [
    {
      id: 1,
      type: 'fire',
      severity: 'critical',
      time: '14:32',
      message: 'Help! There is a huge fire in the Dizengoff Center tunnel, people are trapped!',
      locationName: 'Dizengoff Center, TLV',
      position: [32.0779, 34.7744] // Dizengoff
    },
    {
      id: 2,
      type: 'medical',
      severity: 'high',
      time: '14:30',
      message: 'Someone collapsed on the street, not breathing, send help fast.',
      locationName: 'Rothschild Blvd 22, TLV',
      position: [32.0617, 34.7711] // Rothschild
    },
    {
      id: 3,
      type: 'security',
      severity: 'medium',
      time: '14:15',
      message: 'Suspicious object found near the bus station, please check.',
      locationName: 'Central Bus Station, TLV',
      position: [32.0560, 34.7795] // Central bus station
    }
  ];

  // Mock Volunteers Data (Some dispatched, some available)
  const mockVolunteers = [
    { id: 101, position: [32.0730, 34.7700], status: 'dispatched', assignedTo: 1 }, // Going to fire
    { id: 102, position: [32.0650, 34.7650], status: 'available', assignedTo: null },
    { id: 103, position: [32.0580, 34.7750], status: 'dispatched', assignedTo: 2 }, // Going to medical
    { id: 104, position: [32.0800, 34.7850], status: 'available', assignedTo: null },
    { id: 105, position: [32.0500, 34.7700], status: 'available', assignedTo: null },
    { id: 106, position: [32.0880, 34.7750], status: 'available', assignedTo: null }, // Namir area
    { id: 107, position: [32.0710, 34.7850], status: 'available', assignedTo: null }, // Sarona
    { id: 108, position: [32.0590, 34.7600], status: 'available', assignedTo: null }, // Neve Tzedek
    { id: 109, position: [32.0450, 34.7550], status: 'available', assignedTo: null }, // Jaffa
    { id: 110, position: [32.0620, 34.7800], status: 'available', assignedTo: null }, // Montefiore
    { id: 111, position: [32.0950, 34.7820], status: 'available', assignedTo: null }  // Yarkon Park
  ];

  const [selectedIncident, setSelectedIncident] = useState(null);

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
            {mockIncidents.map(inc => (
              <IncidentCard 
                key={inc.id}
                incident={inc}
                isSelected={selectedIncident?.id === inc.id}
                onClick={setSelectedIncident}
              />
            ))}
          </div>
        </aside>

        {!isLeftOpen && (
          <button className="open-sidebar-btn left" onClick={() => setIsLeftOpen(true)}>
            ❯ Incidents
          </button>
        )}

        {/* Center: Live Map Area */}
        <main className="map-container">
          <MapComponent 
            isLeftOpen={isLeftOpen} 
            isRightOpen={isRightOpen} 
            incidents={mockIncidents}
            volunteers={mockVolunteers}
          />
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
            <AIReasoning incident={selectedIncident} />
          </div>
        </aside>

      </div>
    </div>
  )
}

export default App
