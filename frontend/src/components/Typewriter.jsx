import React, { useState, useEffect } from 'react';
import './Typewriter.css';

const Typewriter = ({ text, speed = 8, delay = 0, id }) => {
  const [displayed, setDisplayed] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [seenIds, setSeenIds] = useState(new Set());

  useEffect(() => {
    if (id && seenIds.has(id)) {
      setDisplayed(text);
      setIsTyping(false);
      return;
    }

    setDisplayed('');
    setIsTyping(true);
    let i = 0;
    
    const startTyping = () => {
      const interval = setInterval(() => {
        setDisplayed(text.substring(0, i + 1));
        i++;
        if (i >= text.length) {
          clearInterval(interval);
          setIsTyping(false);
          if (id) {
            setSeenIds(prev => new Set(prev).add(id));
          }
        }
      }, speed);
      return interval;
    };

    let intervalId;
    const timeoutId = setTimeout(() => {
      intervalId = startTyping();
    }, delay);

    return () => {
      clearTimeout(timeoutId);
      if (intervalId) clearInterval(intervalId);
    };
  }, [text, speed, delay, id]);

  return (
    <span>
      {displayed}
      {isTyping && <span className="cursor-blink">|</span>}
    </span>
  );
};

export default Typewriter;
