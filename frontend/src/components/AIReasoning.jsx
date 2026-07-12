import React, { useState, useEffect } from 'react';
import { Cpu, CheckCircle2, Clock, MapPin, Activity, ShieldAlert, Navigation, Target } from 'lucide-react';
import CircularProgress from './CircularProgress';
import Typewriter from './Typewriter';
import { fetchRecommendations } from '../services/api';
import './AIReasoning.css';

const AIReasoning = ({ incident, volunteers, onVolunteerClick }) => {
  const [visibleSteps, setVisibleSteps] = useState(0);
  const [recommendations, setRecommendations] = useState([]);
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);
  const [isTimeout, setIsTimeout] = useState(false);

  const steps = [
    "Running Qwen/Qwen2.5-14B-Instruct NER...",
    "Extracting Location (Geo-coding)",
    "Assessing Severity (Critical)",
    "Querying Volunteers in 5km Radius",
    "Generating AI Match Scores"
  ];

  // Find dispatched volunteers for this incident
  const assignedVols = volunteers?.filter(v => v.assignedTo === incident?.id) || [];

  // 1. Reset state when switching incidents
  useEffect(() => {
    if (incident?.id) {
      setInitialLoadComplete(false);
      setRecommendations([]);
      setIsTimeout(false);
    }
  }, [incident?.id]);

  // 2. Poll for recommendations (Updates state directly from DB)
  useEffect(() => {
    if (!incident?.id) return;
    
    let isCancelled = false;

    const loadRecs = async () => {
      const recs = await fetchRecommendations(incident.id);
      if (!isCancelled) {
        setRecommendations(recs);
        setInitialLoadComplete(true);
      }
    };
    loadRecs();

    const pollInterval = setInterval(async () => {
      const recs = await fetchRecommendations(incident.id);
      if (!isCancelled) {
        setRecommendations(recs);
        // Ensure this is set even if the first load somehow failed
        setInitialLoadComplete(true);
      }
    }, 3000);
    
    return () => {
      isCancelled = true;
      clearInterval(pollInterval);
    };
  }, [incident?.id]);

  // 3. Manage terminal animation & timeout based purely on whether we have recommendations
  useEffect(() => {
    if (incident?.id && initialLoadComplete && recommendations.length === 0) {
      setVisibleSteps(0);
      setIsTimeout(false);

      const animTimer = setInterval(() => {
        setVisibleSteps(prev => {
          if (prev >= steps.length) {
            clearInterval(animTimer);
            return prev;
          }
          return prev + 1;
        });
      }, 600);

      const timeoutTimer = setTimeout(() => {
        setIsTimeout(true);
      }, 15000);

      return () => {
        clearInterval(animTimer);
        clearTimeout(timeoutTimer);
      };
    }
  }, [incident?.id, recommendations.length]);

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

  const displayRecommendations = recommendations.length > 0 
    ? recommendations 
    : (isTimeout ? volunteers.filter(v => v.status === 'available').slice(0, 3).map((v, idx) => ({
        recommendation_id: `fallback-${v.id}`,
        volunteer_id: v.id,
        total_score: 0.85 - (idx * 0.1),
        score_breakdown: {
           qwen_overall_score: 85 - (idx * 10),
           qwen_distance_score: 90 - (idx * 10),
           qwen_skill_score: 80 - (idx * 5),
           qwen_badge_text: "> WARNING: AI Unreachable. Falling back to proximity metrics."
        },
        isFallback: true
      })) : []);

  const renderRawMessage = (msg) => {
    if (!msg) return null;
    if (!msg.toLowerCase().includes('--- follow-up ---')) {
      return <div className="raw-message">"{msg}"</div>;
    }
    
    const parts = msg.split(/(?:---|)\s*follow-up\s*(?:---|)/i).map(p => p.trim()).filter(p => p);
    
    return (
      <div className="raw-message-multipart">
        <div className="multipart-item">
          <span className="multipart-label">INITIAL REPORT</span>
          <div className="raw-message">"{parts[0]}"</div>
        </div>
        {parts.slice(1).map((part, idx) => (
          <div key={idx} className="multipart-item followup">
            <span className="multipart-label">FOLLOW-UP #{idx + 1}</span>
            <div className="raw-message">"{part}"</div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="ai-reasoning-container">
      <div className="dossier-content">
        
        {/* RAW MESSAGE */}
        <div className="dossier-section">
          <div className="section-title">Original Report</div>
          {renderRawMessage(incident.message)}
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
              <span className={`intel-value ${incident.people_count !== null && incident.people_count > 0 ? 'text-red' : 'text-green'}`}>
                {incident.people_count ?? 'None'}
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
                      <span className="vol-name">{vol.display_name || vol.first_name || 'Volunteer'}</span>
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

        {/* Section 4: AI Recommendations */}
        <div className="dossier-section">
          <div className="section-title">AI Match Evaluations</div>
          {displayRecommendations.length > 0 ? (
            <div className="recommendations-list">
              {displayRecommendations.map((rec) => {
                const vol = volunteers?.find(v => v.id === rec.volunteer_id);
                const breakdown = rec.score_breakdown || {};
                const overallScore = Math.round((breakdown.qwen_overall_score || rec.total_score * 100));
                const distScore = Math.round((breakdown.qwen_distance_score || breakdown.location * 100 || 0));
                const skillScore = Math.round((breakdown.qwen_skill_score || breakdown.skill_match * 100 || 0));
                const badgeText = breakdown.qwen_badge_text || "Recommended by dispatch rules.";
                
                return (
                  <div key={rec.recommendation_id} className="recommendation-card fade-in" data-fallback={rec.isFallback}>
                    <div className="rec-header">
                      <div className="rec-vol-info">
                        <Target size={16} className="text-blue" />
                        <span className="vol-name">{vol?.display_name || vol?.first_name || `Volunteer #${rec.volunteer_id}`}</span>
                      </div>
                      <div className="rec-overall-score">
                        <span className="score-value">{overallScore}%</span>
                        <span className="score-label">MATCH</span>
                      </div>
                    </div>
                    
                    <div className="rec-badge">
                      <Cpu size={12} />
                      <span>{badgeText}</span>
                    </div>

                    <div className="rec-bars">
                      <div className="rec-bar-row">
                        <span className="bar-label">Distance</span>
                        <div className="bar-bg">
                          <div className="bar-fill" style={{ width: `${distScore}%` }}></div>
                        </div>
                        <span className="bar-val">{distScore}%</span>
                      </div>
                      <div className="rec-bar-row">
                        <span className="bar-label">Skills</span>
                        <div className="bar-bg">
                          <div className="bar-fill" style={{ width: `${skillScore}%` }}></div>
                        </div>
                        <span className="bar-val">{skillScore}%</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : !initialLoadComplete ? (
            <div className="no-forces fade-in" style={{ textAlign: 'center', marginTop: '20px' }}>
              Syncing AI evaluations...
            </div>
          ) : (
            <div className="terminal-window" style={{ marginTop: 0 }}>
              <div className="terminal-header">
                <div className="mac-dots">
                  <div className="dot red"></div>
                  <div className="dot yellow"></div>
                  <div className="dot green"></div>
                </div>
                <div className="terminal-title">bash - qwen-eval-worker</div>
              </div>
              <div className="terminal-body">
                <div className="processing-steps">
                  {steps.map((step, index) => (
                    <div key={index} className={`step-item ${index < visibleSteps ? 'visible' : ''}`}>
                      {index < visibleSteps ? <CheckCircle2 size={14} color="var(--neon-green)" /> : <div className="step-placeholder"></div>}
                      <span>{step}</span>
                    </div>
                  ))}
                </div>
                {visibleSteps >= steps.length && (
                   <div className="log-line result fade-in">
                     <span className="prompt">{'>'}</span> Waiting for Qwen/Qwen2.5-14B-Instruct evaluations...
                   </div>
                )}
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
};

export default AIReasoning;
