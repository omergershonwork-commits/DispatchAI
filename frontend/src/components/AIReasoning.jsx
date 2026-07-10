import React, { useState, useEffect } from 'react';
import { Cpu, CheckCircle2 } from 'lucide-react';
import './AIReasoning.css';

const AIReasoning = ({ incident, volunteers }) => {
  const [visibleSteps, setVisibleSteps] = useState(0);

  const steps = [
    "Receiving WhatsApp Text",
    "Running Qwen-2.5 7B NER...",
    "Extracting Location (Geo-coding)",
    "Assessing Severity (Critical)",
    "Querying Volunteers in 5km Radius",
    "Dispatching Closest Matches"
  ];

  // Find dispatched volunteers for this incident
  const assignedVols = volunteers?.filter(v => v.assignedTo === incident?.id) || [];

  // Simulate Qwen "thinking" by revealing steps over time
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
      }, 600); // Reveal a new step every 600ms
      
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

  return (
    <div className="ai-reasoning-container">
      <div className="ai-header">
        <Cpu size={18} className="ai-icon" />
        <span>Incident Dossier #{incident.id}</span>
      </div>

      <div className="dossier-content">
        
        {/* Section 1: Raw Message */}
        <div className="dossier-section">
          <div className="section-title">RAW MESSAGE</div>
          <div className="raw-message">"{incident.message}"</div>
        </div>

        {/* Section 2: AI Intel */}
        <div className="dossier-section">
          <div className="section-title">AI EXTRACTED INTEL</div>
          <div className="intel-tags">
            <span className="intel-tag type">{incident.type.toUpperCase()}</span>
            <span className="intel-tag severity">{incident.severity.toUpperCase()}</span>
            <span className="intel-tag location">📍 {incident.locationName}</span>
            <span className="intel-tag confidence">🟢 98% Confidence</span>
          </div>
        </div>

        {/* Section 3: Dispatched Forces */}
        <div className="dossier-section">
          <div className="section-title">DISPATCHED FORCES</div>
          {assignedVols.length > 0 ? (
            <div className="assigned-forces-list">
              {assignedVols.map(vol => (
                <div key={vol.id} className="mini-volunteer-card">
                  <CheckCircle2 size={14} className="icon-green" />
                  <span>{vol.name}</span>
                  <span className="vol-distance">{vol.distance}</span>
                </div>
              ))}
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
               <span className="prompt">{'>'}</span> ACTION: Dispatched Volunteer #101 to {incident.locationName}.
             </div>
          )}
        </div>
        </div>
      </div>
    </div>
  );
};

export default AIReasoning;
