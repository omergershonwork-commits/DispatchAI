import { useState } from 'react'
import MapComponent from './MapComponent'
import IncidentCard from './components/IncidentCard'
import VolunteerCard from './components/VolunteerCard'
import AIReasoning from './components/AIReasoning'
import { PanelLeftClose, PanelRightClose, AlertTriangle, ShieldAlert, Activity, Users } from 'lucide-react'
import './App.css'

function App() {
  // Mock state for our Top Bar stats
  const [activeIncidentsCount, setActiveIncidentsCount] = useState(0);
  const [availableVolunteersCount, setAvailableVolunteersCount] = useState(50);
  
  // Sidebar states
  const [isLeftOpen, setIsLeftOpen] = useState(true);
  const [isRightOpen, setIsRightOpen] = useState(false); // Closed by default
  const [leftTab, setLeftTab] = useState('incidents'); // 'incidents' or 'forces'

  const handleTabClick = (tab) => {
    if (leftTab === tab && isLeftOpen) {
      setIsLeftOpen(false);
    } else {
      setLeftTab(tab);
      setIsLeftOpen(true);
    }
  };

  const handleIncidentClick = (incident) => {
    setSelectedIncident(incident);
    setIsRightOpen(true); // Open the dossier when an incident is selected
  };

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

  // Mock Volunteers Data
  const mockVolunteers = [
    { id: 101, position: [32.0730, 34.7700], status: 'dispatched', assignedTo: 1, name: 'David Cohen', role: 'Paramedic', distance: '2.1 km' },
    { id: 102, position: [32.0650, 34.7650], status: 'available', assignedTo: null, name: 'Yael Levi', role: 'Rider', distance: '0.5 km' },
    { id: 103, position: [32.0580, 34.7750], status: 'dispatched', assignedTo: 2, name: 'Avi Yitzhak', role: 'Driver', distance: '1.2 km' },
    { id: 104, position: [32.0800, 34.7850], status: 'available', assignedTo: null, name: 'Sarah Aharon', role: 'Paramedic', distance: '4.0 km' },
    { id: 105, position: [32.0500, 34.7700], status: 'available', assignedTo: null, name: 'Moshe Ben-David', role: 'Rider', distance: '3.3 km' },
    { id: 106, position: [32.0880, 34.7750], status: 'available', assignedTo: null, name: 'Maya Golan', role: 'Driver', distance: '5.1 km' },
    { id: 107, position: [32.0710, 34.7850], status: 'available', assignedTo: null, name: 'Ronit Schwartz', role: 'Paramedic', distance: '1.8 km' },
    { id: 108, position: [32.0590, 34.7600], status: 'available', assignedTo: null, name: 'Eli Malka', role: 'Rider', distance: '0.9 km' },
    { id: 109, position: [32.0450, 34.7550], status: 'available', assignedTo: null, name: 'Tamar Edri', role: 'Paramedic', distance: '3.5 km' },
    { id: 110, position: [32.0620, 34.7800], status: 'available', assignedTo: null, name: 'Idan Levy', role: 'Driver', distance: '1.5 km' },
    { id: 111, position: [32.0950, 34.7820], status: 'available', assignedTo: null, name: 'Omer Gershon', role: 'Rider', distance: '6.2 km' }
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

      {/* 2. Main 3-Column Layout with Navigation Rail */}
      <div className="main-content">
        
        {/* Navigation Rail */}
        <nav className="nav-rail">
          <div 
            className={`nav-item ${leftTab === 'incidents' && isLeftOpen ? 'active' : ''}`}
            onClick={() => handleTabClick('incidents')}
            title="Incidents"
          >
            <AlertTriangle size={20} />
          </div>
          <div 
            className={`nav-item ${leftTab === 'forces' && isLeftOpen ? 'active' : ''}`}
            onClick={() => handleTabClick('forces')}
            title="Active Forces"
          >
            <Users size={20} />
          </div>
        </nav>

        {/* Left Sidebar: Dynamic Content */}
        <aside className={`sidebar-left ${!isLeftOpen ? 'collapsed' : ''}`}>
          <div className="panel-header">
            {leftTab === 'incidents' ? 'Active Incidents' : 'Active Forces'}
            <button className="toggle-btn" onClick={() => setIsLeftOpen(false)} title="Close Sidebar">
              ❮
            </button>
          </div>
          <div className="panel-content">
            {leftTab === 'incidents' && mockIncidents.map(inc => (
              <IncidentCard 
                key={inc.id}
                incident={inc}
                isSelected={selectedIncident?.id === inc.id}
                onClick={handleIncidentClick}
              />
            ))}
            {leftTab === 'forces' && mockVolunteers.map(vol => (
              <VolunteerCard key={vol.id} volunteer={vol} />
            ))}
          </div>
        </aside>

        {!isLeftOpen && (
          <button className="open-sidebar-btn left" onClick={() => setIsLeftOpen(true)}>
            ❯
          </button>
        )}

        {/* Center: Map Area */}
        <main className="map-container" style={{ position: 'relative' }}>
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

        {/* Right Sidebar: AI Intelligence */}
        <aside className={`sidebar-right ${!isRightOpen ? 'collapsed' : ''}`}>
          <div className="panel-header">
            <button className="toggle-btn" onClick={() => setIsRightOpen(false)} title="Close Sidebar">
              ❯
            </button>
            AI Intelligence
          </div>
          <div className="panel-content" style={{ padding: 0 }}>
            <AIReasoning incident={selectedIncident} volunteers={mockVolunteers} />
          </div>
        </aside>

      </div>
    </div>
  )
}

export default App
