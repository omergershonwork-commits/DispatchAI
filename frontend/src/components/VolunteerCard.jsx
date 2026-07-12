import React from 'react';
import { User, Activity, Car, Bike } from 'lucide-react';
import './VolunteerCard.css';

const getRoleIcon = (role) => {
  switch (role) {
    case 'Paramedic': return <Activity size={16} strokeWidth={1.5} />;
    case 'Driver': return <Car size={16} strokeWidth={1.5} />;
    case 'Rider': return <Bike size={16} strokeWidth={1.5} />;
    default: return <User size={16} strokeWidth={1.5} />;
  }
};

const VolunteerCard = ({ volunteer, onClick, isSelected }) => {
  const isAvailable = !volunteer.assignedIncidentId;
  const statusClass = volunteer.assignedIncidentId ? 'dispatched' : 'available';

  return (
    <div 
      className={`volunteer-card ${statusClass} ${isSelected ? 'selected' : ''}`}
      onClick={onClick}
    >
      <div className="volunteer-header">
        <div className="volunteer-icon">
          {getRoleIcon(volunteer.role)}
        </div>
        <div className="volunteer-info">
          <span className="volunteer-name">{volunteer.display_name || volunteer.first_name || 'Volunteer'}</span>
          <span className="volunteer-role">{volunteer.role}</span>
        </div>
        <div className="volunteer-distance">
          {volunteer.distance}
        </div>
      </div>
      
      {!isAvailable && volunteer.assignedIncidentId && volunteer.dispatchStatus !== 'accepted' && (
        <div className="volunteer-footer">
          <span className="status-dot pulsing"></span>
          <span>Dispatched to Incident #{volunteer.assignedIncidentId}</span>
        </div>
      )}

      {!isAvailable && volunteer.assignedIncidentId && volunteer.dispatchStatus === 'accepted' && (
        <div className="volunteer-footer accepted" style={{ color: 'var(--tactical-green)' }}>
          <span className="status-dot green pulsing" style={{ boxShadow: '0 0 8px var(--tactical-green)' }}></span>
          <span>Confirmed & En Route to #{volunteer.assignedIncidentId}</span>
        </div>
      )}
      
      {isAvailable && (
        <div className="volunteer-footer available">
          <span className="status-dot green"></span>
          <span>Available for Dispatch</span>
        </div>
      )}
    </div>
  );
};

export default VolunteerCard;
