import React from 'react';
import { AlertTriangle, ShieldAlert, Activity, MapPin } from 'lucide-react';
import './IncidentCard.css';

const getIcon = (type) => {
  switch (type) {
    case 'fire': return <AlertTriangle size={18} strokeWidth={1.5} />;
    case 'medical': return <Activity size={18} strokeWidth={1.5} />;
    default: return <ShieldAlert size={18} strokeWidth={1.5} />;
  }
};

const IncidentCard = ({ incident, onClick, isSelected }) => {
  const parseSynthesis = (text) => {
    if (!text) return 'Pending Analysis...';
    const analysisMatch = text.match(/• ANALYSIS:\n(.*?)(?=\n\n• ACTION TAKEN:|$)/s);
    return analysisMatch ? analysisMatch[1].trim() : text;
  };
  
  const analysisText = parseSynthesis(incident.aiSynthesis);

  return (
    <div 
      className={`incident-card ${incident.urgency} ${isSelected ? 'selected' : ''}`}
      onClick={() => onClick(incident)}
    >
      <div className="card-header">
        <div className="title-group">
          <div className="card-icon">{getIcon(incident.type)}</div>
          <h3>Incident #{incident.id}</h3>
        </div>
        <div className="header-right">
          <div className="card-time">{incident.time}</div>
          <div className={`severity-badge ${incident.urgency}`}>{incident.urgency.toUpperCase()}</div>
        </div>
      </div>
      <div className="card-body">
        <p className="message-text">{analysisText}</p>
      </div>
      <div className="card-footer">
        <MapPin size={14} strokeWidth={1.5} />
        <span>{incident.locationName}</span>
      </div>
    </div>
  );
};

export default IncidentCard;
