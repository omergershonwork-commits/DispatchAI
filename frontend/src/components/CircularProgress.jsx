import React, { useEffect, useState } from 'react';
import './CircularProgress.css';

const CircularProgress = ({ value, size = 48, strokeWidth = 3, color = "#10b981" }) => {
  const [progress, setProgress] = useState(0); 
  const [displayValue, setDisplayValue] = useState(0); 
  const radius = (size - strokeWidth) / 2 - 2; 
  const circumference = radius * 2 * Math.PI;

  useEffect(() => {
    setProgress(0);
    setDisplayValue(0);

    const animationDuration = 1000; 
    let startTime;
    let animationFrame;

    const timeout = setTimeout(() => {
      setProgress(value);
      
      const animateCount = (timestamp) => {
        if (!startTime) startTime = timestamp;
        const elapsed = timestamp - startTime;
        const progressRatio = Math.min(elapsed / animationDuration, 1);
        
        const easeOutQuad = t => t * (2 - t);
        setDisplayValue(Math.floor(easeOutQuad(progressRatio) * value));

        if (progressRatio < 1) {
          animationFrame = requestAnimationFrame(animateCount);
        } else {
          setDisplayValue(value);
        }
      };
      
      animationFrame = requestAnimationFrame(animateCount);
    }, 150);

    return () => {
      clearTimeout(timeout);
      if (animationFrame) cancelAnimationFrame(animationFrame);
    };
  }, [value]);

  const strokeDashoffset = circumference - (progress / 100) * circumference;

  return (
    <div className="circular-progress-container" style={{ width: size, height: size }}>
      {progress > 0 && <div className="circular-pulse" style={{ borderColor: color, width: size, height: size }}></div>}
      <svg className="circular-progress-svg" width={size} height={size}>
        <defs>
          <linearGradient id="cyber-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={color} stopOpacity="0.2" />
            <stop offset="100%" stopColor={color} stopOpacity="1" />
          </linearGradient>
          <filter id="cyber-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>
        {/* Faint Background track */}
        <circle
          stroke="rgba(255, 255, 255, 0.03)"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          fill="none"
        />
        {/* Actual progress */}
        <circle
          stroke="url(#cyber-gradient)"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          filter="url(#cyber-glow)"
          style={{ transition: 'stroke-dashoffset 1s cubic-bezier(0.165, 0.84, 0.44, 1)' }}
        />
      </svg>
      <div className="circular-progress-content">
        <span className="circular-progress-value" style={{ color: 'rgba(255, 255, 255, 0.75)' }}>{displayValue}%</span>
      </div>
    </div>
  );
};

export default CircularProgress;
