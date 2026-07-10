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
      siteAccessibility: 'Underground (Restricted)',
      aiConfidence: 96,
      casualties: 'Unknown (High Potential)',
      requiredEquipment: ['Burn Kits', 'Oxygen', 'Fire Extinguishers'],
      time: '14:32',
      message: 'Help! There is a huge fire in the Dizengoff Center tunnel, people are trapped!',
      locationName: 'Dizengoff Center, TLV',
      position: [32.0779, 34.7744], // Dizengoff
      aiSynthesis: "Report analyzed: Large-scale fire in an enclosed public space (Dizengoff Center tunnel). Due to reports of trapped individuals, urgency is elevated to CRITICAL. Action taken: Dispatched 3 motorcycle-based paramedics, in order to bypass anticipated heavy traffic.",
      timeline: [
        { time: '14:32', event: 'Received distress WhatsApp message.', active: false },
        { time: '14:32', event: 'AI parsed location and assessed CRITICAL severity.', active: false },
        { time: '14:33', event: 'AI automatically dispatched 3 nearest riders.', active: false },
        { time: '14:34', event: '2 Volunteers confirmed En Route.', active: true }
      ]
    },
    {
      id: 2,
      type: 'medical',
      severity: 'high',
      siteAccessibility: 'Open Street (Traffic)',
      aiConfidence: 99,
      casualties: '1 (Unconscious)',
      requiredEquipment: ['Defibrillator (AED)', 'BLS Kit'],
      time: '14:30',
      message: 'Someone collapsed on the street, not breathing, send help fast.',
      locationName: 'Rothschild Blvd 22, TLV',
      position: [32.0617, 34.7711], // Rothschild
      aiSynthesis: "Report analyzed: Unconscious, non-breathing individual on the street. Diagnosis: Suspected cardiac arrest. Action taken: Dispatched nearest available volunteers equipped with AEDs, for immediate resuscitation.",
      timeline: [
        { time: '14:30', event: 'Received emergency report.', active: false },
        { time: '14:31', event: 'AI identified cardiac arrest indicators.', active: false },
        { time: '14:31', event: 'Dispatched 2 volunteers with AEDs.', active: false },
        { time: '14:35', event: 'Volunteer arrived On Scene.', active: true }
      ]
    },
    {
      id: 3,
      type: 'security',
      severity: 'medium',
      siteAccessibility: 'Crowded Hub',
      aiConfidence: 82,
      casualties: 'None',
      requiredEquipment: ['Radio', 'Observation Kit'],
      time: '14:15',
      message: 'Suspicious object found near the bus station, please check.',
      locationName: 'Central Bus Station, TLV',
      position: [32.0560, 34.7795], // Central bus station
      aiSynthesis: "Report analyzed: Suspicious object located in a high-traffic transit hub. Action taken: Dispatched reconnaissance volunteer for visual verification, prior to bomb squad escalation.",
      timeline: [
        { time: '14:15', event: 'Received suspicious object report.', active: false },
        { time: '14:16', event: 'AI dispatched 1 reconnaissance volunteer.', active: false },
        { time: '14:20', event: 'Volunteer is On Scene, investigating.', active: true }
      ]
    }
  ];

  // Mock Volunteers Data
  const mockVolunteers = [
    { id: 101, position: [32.0730, 34.7700], status: 'en_route', assignedTo: 1, name: 'David Cohen', role: 'Paramedic', distance: '2.1 km' },
    { id: 102, position: [32.0650, 34.7650], status: 'available', assignedTo: null, name: 'Yael Levi', role: 'Rider', distance: '0.5 km' },
    { id: 103, position: [32.0580, 34.7750], status: 'on_scene', assignedTo: 2, name: 'Avi Yitzhak', role: 'Driver', distance: '1.2 km' },
    { id: 104, position: [32.0800, 34.7850], status: 'waiting', assignedTo: 1, name: 'Sarah Aharon', role: 'Paramedic', distance: '4.0 km' },
    { id: 105, position: [32.0500, 34.7700], status: 'available', assignedTo: null, name: 'Moshe Ben-David', role: 'Rider', distance: '3.3 km' },
    { id: 106, position: [32.0880, 34.7750], status: 'en_route', assignedTo: 1, name: 'Maya Golan', role: 'Rider', distance: '5.1 km' },
    { id: 107, position: [32.0710, 34.7850], status: 'available', assignedTo: null, name: 'Ronit Schwartz', role: 'Paramedic', distance: '1.8 km' },
    { id: 108, position: [32.0590, 34.7600], status: 'waiting', assignedTo: 2, name: 'Eli Malka', role: 'Rider', distance: '0.9 km' },
    { id: 109, position: [32.0450, 34.7550], status: 'available', assignedTo: null, name: 'Tamar Edri', role: 'Paramedic', distance: '3.5 km' },
    { id: 110, position: [32.0620, 34.7800], status: 'on_scene', assignedTo: 3, name: 'Idan Levy', role: 'Driver', distance: '1.5 km' },
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
