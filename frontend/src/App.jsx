import { useState, useEffect } from 'react'
import MapComponent from './MapComponent'
import IncidentCard from './components/IncidentCard'
import VolunteerCard from './components/VolunteerCard'
import AIReasoning from './components/AIReasoning'
import VolunteerDossier from './components/VolunteerDossier'
import { PanelLeftClose, PanelRightClose, AlertTriangle, ShieldAlert, Activity, Users, Crosshair } from 'lucide-react'
import { fetchIncidents, fetchVolunteers, dispatchVolunteer } from './services/api'
import './App.css'

function App() {
  const [isLeftOpen, setIsLeftOpen] = useState(true);
  const [isRightOpen, setIsRightOpen] = useState(false); // Closed by default
  const [leftTab, setLeftTab] = useState('incidents'); // 'incidents' or 'forces'
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [selectedVolunteer, setSelectedVolunteer] = useState(null);
  const [activeDossier, setActiveDossier] = useState(null); // 'incident' or 'volunteer'

  // Command & Control Override State
  const [isCommandMode, setIsCommandMode] = useState(false);
  const [dispatchSource, setDispatchSource] = useState(null); // stores volunteer id when waiting for incident click

  const handleTabClick = (tab) => {
    if (leftTab === tab && isLeftOpen) {
      setIsLeftOpen(false);
    } else {
      setLeftTab(tab);
      setIsLeftOpen(true);
      // Switch right panel automatically if we have a selection in that tab
      if (tab === 'incidents' && selectedIncident) setIsRightOpen(true);
      if (tab === 'forces' && selectedVolunteer) setIsRightOpen(true);
    }
  };

  const handleIncidentClick = (incident, keepRightVolunteer = false) => {
    if (isCommandMode && dispatchSource) {
      handleManualDispatch(dispatchSource, incident.id);
      setDispatchSource(null);
      return;
    }

    setSelectedIncident(incident);
    setLeftTab('incidents');
    if (!keepRightVolunteer && !isCommandMode) {
      setLeftTab('incidents');
      setActiveDossier('incident');
      setIsRightOpen(true);
      setSelectedVolunteer(null);
    } else if (keepRightVolunteer && !isCommandMode) {
      setActiveDossier('volunteer');
      setIsRightOpen(true);
      if (leftTab === 'incidents') {
        setSelectedVolunteer(null);
      }
    }
  };

  const handleVolunteerClick = (volunteer, keepTab = false) => {
    if (isCommandMode) {
      setDispatchSource(volunteer.id);
    }

    setSelectedVolunteer(volunteer);
    if (!keepTab && !isCommandMode) {
      setLeftTab('forces');
      setActiveDossier('volunteer');
      setIsRightOpen(true);
      setSelectedIncident(null);
    } else if (keepTab && !isCommandMode) {
      setActiveDossier('volunteer');
      setIsRightOpen(true);
      if (leftTab === 'forces') {
        setSelectedIncident(null);
      }
    }
  };

  const [incidents, setIncidents] = useState([]);
  const [volunteers, setVolunteers] = useState([]);

  useEffect(() => {
    // Initial fetch
    const loadData = async () => {
      const incData = await fetchIncidents();
      setIncidents(incData);
      
      const volData = await fetchVolunteers();
      setVolunteers(volData);
    };
    loadData();

    // Polling for incidents (3 seconds)
    const incInterval = setInterval(async () => {
      const incData = await fetchIncidents();
      setIncidents(prev => {
        // Prevent state flickering if incident list hasn't changed structurally
        return incData;
      });
      // If we have a selected incident, update its content so the right panel reflects changes
      setSelectedIncident(prevSelected => {
        if (!prevSelected) return null;
        return incData.find(inc => inc.id === prevSelected.id) || prevSelected;
      });
    }, 3000);

    // Polling for volunteers (30 seconds)
    const volInterval = setInterval(async () => {
      const volData = await fetchVolunteers();
      setVolunteers(volData);
      
      setSelectedVolunteer(prevSelected => {
        if (!prevSelected) return null;
        return volData.find(vol => vol.id === prevSelected.id) || prevSelected;
      });
    }, 30000);

    return () => {
      clearInterval(incInterval);
      clearInterval(volInterval);
    };
  }, []);

  const handleManualDispatch = async (volId, incId) => {
    // Optimistic UI update
    setVolunteers(prev => prev.map(v => 
      v.id === volId 
        ? { ...v, status: 'dispatched', assignedTo: incId } 
        : v
    ));
    await dispatchVolunteer(volId, incId);
  };

  const activeIncidentsCount = incidents.length;
  const availableVolunteersCount = volunteers.filter(v => v.status === 'available').length;

  return (
    <div className={`app-container ${isCommandMode ? 'command-mode-active' : ''}`}>
      {/* 1. Top Navigation & Stats Bar */}
      <header className="topbar">
        <div className="topbar-logo" style={{ position: 'relative' }}>
          Dispatch <span className="logo-accent">AI</span>
          <button 
            className="command-mode-toggle" 
            onClick={() => {
              setIsCommandMode(!isCommandMode);
              setDispatchSource(null);
            }}
            title="Toggle Command Override"
          >
            <Crosshair size={14} />
          </button>
        </div>
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
            {leftTab === 'incidents' ? (
              <div className="list-container">
                {incidents.map(inc => (
                  <IncidentCard 
                    key={inc.id} 
                    incident={inc} 
                    isSelected={selectedIncident?.id === inc.id}
                    onClick={() => handleIncidentClick(inc)}
                  />
                ))}
              </div>
            ) : (
              <div className="list-container">
                {volunteers.map(vol => (
                  <VolunteerCard 
                    key={vol.id} 
                    volunteer={vol} 
                    isSelected={selectedVolunteer?.id === vol.id}
                    onClick={() => handleVolunteerClick(vol, true)}
                  />
                ))}
              </div>
            )}
          </div>
        </aside>

        {!isLeftOpen && (
          <button className="open-sidebar-btn left" onClick={() => setIsLeftOpen(true)}>
            ❯
          </button>
        )}

        {/* Map Area */}
        <main className={`map-container ${isCommandMode && dispatchSource ? 'dispatching' : ''}`} style={{ flex: 1, position: 'relative' }}>
          {isCommandMode && (
            <div className="command-mode-banner">
              MANUAL OVERRIDE ACTIVE {dispatchSource && '- AWAITING TARGET'}
            </div>
          )}
          <MapComponent 
            isLeftOpen={isLeftOpen} 
            isRightOpen={isRightOpen} 
            incidents={incidents} 
            volunteers={volunteers}
            selectedVolunteer={selectedVolunteer}
            selectedIncident={selectedIncident}
            leftTab={leftTab}
            isCommandMode={isCommandMode}
            dispatchSource={dispatchSource}
            onVolunteerClick={handleVolunteerClick}
            onIncidentClick={handleIncidentClick}
          />
        </main>

        {!isRightOpen && (
          <button className="open-sidebar-btn right" onClick={() => setIsRightOpen(true)}>
            AI Reasoning ❮
          </button>
        )}

        {/* Right Sidebar: Dossier (Incident or Volunteer) */}
        <aside className={`sidebar-right ${!isRightOpen ? 'collapsed' : ''}`}>
          <div className="panel-header">
            {activeDossier === 'incident' ? 'Incident Dossier' : 'Volunteer Dossier'}
            <button className="toggle-btn" onClick={() => setIsRightOpen(false)} title="Close Dossier">
              ❯
            </button>
          </div>
          <div className="panel-content" style={{ padding: 0 }}>
            {activeDossier === 'incident' && <AIReasoning incident={selectedIncident} volunteers={volunteers} onVolunteerClick={handleVolunteerClick} />}
            {activeDossier === 'volunteer' && <VolunteerDossier volunteer={selectedVolunteer} incident={incidents.find(i => i.id === selectedVolunteer?.assignedTo)} onIncidentClick={handleIncidentClick} />}
          </div>
        </aside>

      </div>
    </div>
  )
}

export default App
