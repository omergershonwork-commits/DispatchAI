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

const VolunteerCard = ({ volunteer }) => {
  const isAvailable = volunteer.status === 'available';

  return (
    <div className={`volunteer-card ${volunteer.status}`}>
      <div className="volunteer-header">
        <div className="volunteer-icon">
          {getRoleIcon(volunteer.role)}
        </div>
        <div className="volunteer-info">
          <span className="volunteer-name">{volunteer.name}</span>
          <span className="volunteer-role">{volunteer.role}</span>
        </div>
        <div className="volunteer-distance">
          {volunteer.distance}
        </div>
      </div>
      
      {!isAvailable && volunteer.assignedTo && (
        <div className="volunteer-footer">
          <span className="status-dot pulsing"></span>
          <span>Dispatched to Incident #{volunteer.assignedTo}</span>
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
