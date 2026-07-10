import React, { useState } from 'react';
import { ChevronUp, ChevronDown, Activity, Car, Bike, User } from 'lucide-react';
import VolunteerCard from './VolunteerCard';
import './BottomRoster.css';

const BottomRoster = ({ volunteers }) => {
  const [isOpen, setIsOpen] = useState(false);

  const availableCount = volunteers.filter(v => v.status === 'available').length;
  const dispatchedCount = volunteers.filter(v => v.status === 'dispatched').length;

  return (
    <div className={`bottom-roster ${isOpen ? 'open' : 'closed'}`}>
      <div className="roster-header" onClick={() => setIsOpen(!isOpen)}>
        <div className="roster-summary">
          <span className="summary-badge available">
            <span className="status-dot green"></span>
            {availableCount} Available
          </span>
          <span className="summary-badge dispatched">
            <span className="status-dot pulsing"></span>
            {dispatchedCount} Dispatched
          </span>
        </div>
        <div className="roster-toggle">
          {isOpen ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
          <span className="toggle-text">{isOpen ? 'Hide Roster' : 'Show Roster'}</span>
        </div>
      </div>
      
      <div className="roster-content">
        {volunteers.map(vol => (
          <VolunteerCard key={vol.id} volunteer={vol} />
        ))}
      </div>
    </div>
  );
};

export default BottomRoster;
