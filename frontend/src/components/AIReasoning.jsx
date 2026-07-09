import React, { useState, useEffect } from 'react';
import { Cpu, CheckCircle2 } from 'lucide-react';
import './AIReasoning.css';

const AIReasoning = ({ incident }) => {
  const [visibleSteps, setVisibleSteps] = useState(0);

  const steps = [
    "Receiving WhatsApp Text",
    "Extracting Location (NER)",
    "Assessing Severity",
    "Querying Volunteers in 5km Radius",
    "Dispatching Closest Match"
  ];

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
        <span>Qwen-2.5 7B Analysis</span>
      </div>
      
      <div className="terminal-window">
        <div className="terminal-header">
          <span className="dot red"></span>
          <span className="dot yellow"></span>
          <span className="dot green"></span>
        </div>
        <div className="terminal-body">
          <div className="log-line text-input">
            <span className="prompt">{'>'}</span> Input: "{incident.message}"
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
  );
};

export default AIReasoning;
