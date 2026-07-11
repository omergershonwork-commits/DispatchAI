import React, { useState, useEffect } from 'react';
import { Cpu, CheckCircle2, Clock, MapPin, Activity, ShieldAlert, Navigation } from 'lucide-react';
import CircularProgress from './CircularProgress';
import Typewriter from './Typewriter';
import './AIReasoning.css';
const AIReasoning = ({ incident, volunteers, onVolunteerClick }) => {
  const [visibleSteps, setVisibleSteps] = useState(0);

  const steps = [
    "Running Qwen-2.5 7B NER...",
    "Extracting Location (Geo-coding)",
    "Assessing Severity (Critical)",
    "Querying Volunteers in 5km Radius",
    "Dispatching Closest Matches"
  ];

  // Find dispatched volunteers for this incident
  const assignedVols = volunteers?.filter(v => v.assignedTo === incident?.id) || [];

  useEffect(() => {
    if (incident) {
      setVisibleSteps(0);
      const timer = setInterval(() => {
        setVisibleSteps(prev => {
          if (prev >= steps.length) {
            clearInterval(timer);
            return prev;
          }
          return prev + 1;
        });
      }, 600);
      return () => clearInterval(timer);
    }
  }, [incident]);

  if (!incident) {
    return (
      <div className="ai-empty-state">
        <Cpu size={48} opacity={0.2} />
        <p>Select an incident to view Qwen's real-time reasoning.</p>
      </div>
    );
  }

  const parseSynthesis = (text) => {
    if (!text) return { analysis: '', action: null };
    const analysisMatch = text.match(/• ANALYSIS:\n(.*?)(?=\n\n• ACTION TAKEN:|$)/s);
    const actionMatch = text.match(/• ACTION TAKEN:\n(.*)/s);
    return {
      analysis: analysisMatch ? analysisMatch[1].trim() : text,
      action: actionMatch ? actionMatch[1].trim() : null
    };
  };

  const { analysis, action } = parseSynthesis(incident?.aiSynthesis);

  return (
    <div className="ai-reasoning-container">
      <div className="dossier-content">
        
        {/* RAW MESSAGE */}
        <div className="dossier-section">
          <div className="section-title">Incoming Distress Signal</div>
          <div className="raw-message">"{incident.message}"</div>
        </div>

        {/* AI SYNTHESIS - FUTURISTIC MODULES */}
        <div className="synthesis-nodes">
          <div className="synthesis-node analysis-node">
            <div className="node-header">
              <Activity size={14} className="node-icon pulsing" />
              <span className="node-title">AI ANALYSIS</span>
            </div>
            <div className="node-body">
              <Typewriter id={`analysis-${incident.id}`} text={analysis} speed={6} />
            </div>
          </div>
          
          {action && (
            <div className="synthesis-node action-node">
              <div className="node-header">
                <Navigation size={14} className="node-icon pulsing" />
                <span className="node-title">ACTION PROTOCOL</span>
              </div>
              <div className="node-body">
                 <Typewriter id={`action-${incident.id}`} text={action} speed={6} delay={analysis.length * 6 + 150} />
              </div>
            </div>
          )}
        </div>

        {/* INTEL GRID */}
        <div className="dossier-section">
          <div className="section-title">Extracted Intel</div>
          <div className="intel-grid">
            <div className="intel-box">
              <span className="intel-label">AI Confidence</span>
              <CircularProgress key={incident.id} value={incident.aiConfidence} color="#10b981" />
            </div>
            <div className="intel-box">
              <span className="intel-label">Site Access</span>
              <span className="intel-value text-orange">
                {incident.siteAccessibility}
              </span>
            </div>
            <div className="intel-box">
              <span className="intel-label">Est. Casualties</span>
              <span className={`intel-value ${incident.casualties !== 'None' ? 'text-red' : 'text-green'}`}>
                {incident.casualties}
              </span>
            </div>
            <div className="intel-box">
              <span className="intel-label">Required Gear</span>
              <span className="intel-value text-blue">
                {incident.requiredEquipment?.join(', ')}
              </span>
            </div>
          </div>
        </div>

        {/* TIMELINE */}
        <div className="dossier-section">
          <div className="section-title">Event Timeline</div>
          <div className="timeline-container">
            {incident.timeline?.map((item, idx) => (
              <div key={idx} className={`timeline-item ${item.active ? 'active' : ''}`}>
                <div className="timeline-dot"></div>
                <div className="timeline-time">{item.time}</div>
                <div className="timeline-text">{item.event}</div>
              </div>
            ))}
          </div>
        </div>

        {/* DISPATCHED FORCES */}
        <div className="dossier-section">
          <div className="section-title">Assigned Forces Status</div>
          {assignedVols.length > 0 ? (
            <div className="assigned-forces-list">
              {assignedVols.map(vol => {
                let statusColor = 'var(--text-secondary)';
                let statusIcon = <CheckCircle2 size={14} color={statusColor} />;
                let statusText = 'Unknown';
                
                if (vol.status === 'on_scene') {
                  statusColor = 'var(--tactical-blue)';
                  statusIcon = <MapPin size={14} color={statusColor} />;
                  statusText = 'On Scene';
                } else if (vol.status === 'en_route') {
                  statusColor = 'var(--tactical-green)';
                  statusIcon = <Navigation size={14} color={statusColor} />;
                  statusText = 'En Route';
                } else if (vol.status === 'waiting') {
                  statusColor = 'var(--tactical-orange)';
                  statusIcon = <Clock size={14} color={statusColor} />;
                  statusText = 'Waiting Reply';
                }

                return (
                  <div 
                    key={vol.id} 
                    className="mini-volunteer-card" 
                    style={{ borderColor: statusColor, cursor: 'pointer' }}
                    onClick={() => onVolunteerClick && onVolunteerClick(vol, true)}
                    title="Click to view volunteer dossier"
                  >
                    {statusIcon}
                    <div className="vol-details">
                      <span className="vol-name">{vol.name}</span>
                      <span className="vol-status-text" style={{ color: statusColor }}>{statusText}</span>
                    </div>
                    <span className="vol-distance">{vol.distance}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="no-forces">Waiting for AI assignment...</div>
          )}
        </div>

        {/* Section 4: AI Terminal */}
        <div className="terminal-window">
          <div className="terminal-header">
            <span className="dot red"></span>
            <span className="dot yellow"></span>
            <span className="dot green"></span>
            <span className="terminal-title">Qwen-2.5 Logic</span>
          </div>
          <div className="terminal-body">
            <div className="log-line text-input">
              <span className="prompt">{'>'}</span> Processing Event...
            </div>
          
            <div className="processing-steps">
              {steps.map((step, index) => (
                <div 
                  key={index} 
                  className={`step-item ${index < visibleSteps ? 'visible' : ''}`}
                >
                  {index < visibleSteps ? (
                     <CheckCircle2 size={14} color="var(--neon-green)" />
                  ) : (
                     <div className="step-placeholder"></div>
                  )}
                  <span>{step}</span>
                </div>
              ))}
            </div>

            {visibleSteps >= steps.length && (
               <div className="log-line result fade-in">
                 <span className="prompt">{'>'}</span> ACTION: Dispatched {assignedVols.length} Volunteers to {incident.locationName}.
               </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};

export default AIReasoning;
