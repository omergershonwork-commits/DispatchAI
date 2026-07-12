import React, { useState } from 'react';
import { Activity, Battery, CheckCircle2, MapPin, Clock, ShieldAlert, Award, User, Stethoscope, Car, Navigation } from 'lucide-react';
import './VolunteerDossier.css';

const VolunteerDossier = ({ volunteer, incident, onIncidentClick }) => {
  if (!volunteer) {
    return (
      <div className="ai-empty-state">
        <User size={48} opacity={0.2} />
        <p>Select a volunteer to view their detailed dossier.</p>
      </div>
    );
  }

  let statusColor = 'var(--text-secondary)';
  let statusText = 'Available';
  let statusIcon = <CheckCircle2 size={16} color={statusColor} />;

  if (volunteer.status === 'on_scene') {
    statusColor = 'var(--tactical-blue)';
    statusText = 'On Scene';
    statusIcon = <MapPin size={16} color={statusColor} />;
  } else if (volunteer.status === 'en_route') {
    statusColor = 'var(--tactical-green)';
    statusText = 'En Route';
    statusIcon = <Navigation size={16} color={statusColor} />;
  } else if (volunteer.status === 'waiting') {
    statusColor = 'var(--tactical-orange)';
    statusText = 'Waiting Reply';
    statusIcon = <Clock size={16} color={statusColor} />;
  } else if (volunteer.status === 'available') {
    statusColor = 'var(--neon-green)';
    statusText = 'Available / Patrol';
    statusIcon = <CheckCircle2 size={16} color={statusColor} />;
  }

  const CensoredPhone = ({ phone }) => {
    const [revealed, setRevealed] = useState(false);
    if (!phone) return <span className="intel-value" style={{ color: 'var(--text-secondary)' }}>N/A</span>;
    if (revealed) return <span className="intel-value text-blue" style={{ cursor: 'pointer', letterSpacing: '1px' }} onClick={() => setRevealed(false)}>{phone}</span>;
    return <span className="intel-value text-blue" style={{ cursor: 'pointer', letterSpacing: '2px', filter: 'blur(4px)', userSelect: 'none' }} onClick={() => setRevealed(true)}>05X-XXXXXXX</span>;
  };

  return (
    <div className="volunteer-dossier-container">
      <div className="dossier-content">
        
        {/* Profile Header */}
        <div className="dossier-section profile-header">
          <div className="profile-avatar">
            <User size={32} color="var(--tactical-blue)" />
          </div>
          <div className="profile-info">
            <div className="profile-name">{volunteer.display_name || volunteer.first_name || 'Volunteer'}</div>
            <div className="profile-role">{volunteer.role}</div>
            <div className="profile-status" style={{ color: statusColor }}>
              {statusIcon}
              <span>{statusText}</span>
            </div>
          </div>
        </div>

        {/* Biodata */}
        <div className="dossier-section">
          <div className="section-title">Operator Intel</div>
          <div className="intel-grid bio-grid">
            <div className="intel-box">
              <span className="intel-label">Phone (Tap to reveal)</span>
              <CensoredPhone phone={volunteer.phone} />
            </div>
            <div className="intel-box">
              <span className="intel-label">Telegram Handle</span>
              <span className="intel-value">{volunteer.username ? `@${volunteer.username}` : 'N/A'}</span>
            </div>
            <div className="intel-box" style={{ gridColumn: 'span 2' }}>
              <span className="intel-label">Last Active</span>
              <span className="intel-value">{volunteer.lastSeen}</span>
            </div>
          </div>
        </div>

        {/* Performance Stats */}
        <div className="dossier-section">
          <div className="section-title">Performance Stats</div>
          <div className="intel-grid telemetry-grid">
            <div className="intel-box">
              <span className="intel-label"><Activity size={12} className="inline-icon"/> Trust Score</span>
              <span className="intel-value text-green">
                {volunteer.trustScore}
              </span>
            </div>
            <div className="intel-box">
              <span className="intel-label"><CheckCircle2 size={12} className="inline-icon"/> Incidents Handled</span>
              <span className="intel-value text-blue">
                {volunteer.incidentsHandled}
              </span>
            </div>
          </div>
        </div>

        {/* Readiness Grid */}
        <div className="dossier-section">
          <div className="section-title">Asset Readiness</div>
          <div className="readiness-list">
            <div className="readiness-item">
              <Car size={16} className="readiness-icon" />
              <div className="readiness-details">
                <span className="readiness-label">Transport</span>
                <span className="readiness-value">{volunteer.vehicle}</span>
              </div>
            </div>
            <div className="readiness-item">
              <Stethoscope size={16} className="readiness-icon" />
              <div className="readiness-details">
                <span className="readiness-label">Inventory</span>
                <span className="readiness-value">{volunteer.equipment?.join(', ')}</span>
              </div>
            </div>
            <div className="readiness-item">
              <Award size={16} className="readiness-icon" />
              <div className="readiness-details">
                <span className="readiness-label">Specializations</span>
                <span className="readiness-value">{volunteer.skills?.join(', ')}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Current Assignment */}
        {incident && (
          <div className="dossier-section">
            <div className="section-title">Current Assignment</div>
            <div 
              className="assignment-card"
              onClick={() => onIncidentClick && onIncidentClick(incident, true)}
              style={{ cursor: 'pointer' }}
              title="Click to view incident in left panel"
            >
              <ShieldAlert size={20} color="var(--tactical-red)" />
              <div className="assignment-details">
                <div className="assignment-id">Incident #{incident.id} - {incident.type.toUpperCase()}</div>
                <div className="assignment-location">{incident.locationName}</div>
                <div className="assignment-distance">Distance from target: <span className="text-orange">{volunteer.distance}</span></div>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

export default VolunteerDossier;
