import React from 'react';
import { Flame, ShieldAlert, HeartPulse, MapPin } from 'lucide-react';
import './IncidentCard.css';

const getIcon = (type) => {
  switch (type) {
    case 'fire': return <Flame size={20} />;
    case 'medical': return <HeartPulse size={20} />;
    default: return <ShieldAlert size={20} />;
  }
};

const IncidentCard = ({ incident, onClick, isSelected }) => {
  return (
    <div 
      className={`incident-card ${incident.severity} ${isSelected ? 'selected' : ''}`}
      onClick={() => onClick(incident)}
    >
      <div className="card-header">
        <div className="card-icon">{getIcon(incident.type)}</div>
        <div className="card-time">{incident.time}</div>
        <div className={`severity-badge ${incident.severity}`}>{incident.severity.toUpperCase()}</div>
      </div>
      <div className="card-body">
        <p className="message-text">"{incident.message}"</p>
      </div>
      <div className="card-footer">
        <MapPin size={14} />
        <span>{incident.locationName}</span>
      </div>
    </div>
  );
};

export default IncidentCard;
