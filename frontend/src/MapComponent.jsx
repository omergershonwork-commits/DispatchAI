import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Polyline, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { renderToString } from 'react-dom/server';
import { Flame, ShieldAlert, Crosshair, HeartPulse } from 'lucide-react';

// Helper component to force Leaflet to recalculate its size
const MapResizer = ({ isLeftOpen, isRightOpen }) => {
  const map = useMap();
  useEffect(() => {
    const timeout = setTimeout(() => {
      map.invalidateSize();
    }, 350);
    return () => clearTimeout(timeout);
  }, [isLeftOpen, isRightOpen, map]);
  return null;
};

// Create custom Emergency Icon using Lucide and our CSS classes
const createEmergencyIcon = (severityClass, IconComponent) => {
  const iconHtml = renderToString(<IconComponent size={20} color="white" />);
  return L.divIcon({
    className: 'custom-icon-wrapper', // Removes default Leaflet white square background
    html: `<div class="emergency-marker ${severityClass}" style="width: 40px; height: 40px;">${iconHtml}</div>`,
    iconSize: [40, 40],
    iconAnchor: [20, 20],
  });
};

// Create custom Volunteer Icon
const createVolunteerIcon = (statusClass) => {
  return L.divIcon({
    className: 'custom-icon-wrapper',
    html: `<div class="volunteer-marker ${statusClass}" style="width: 16px; height: 16px;"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });
};

const MapComponent = ({ isLeftOpen, isRightOpen }) => {
  // Center of Tel Aviv
  const centerPosition = [32.0853, 34.7818];

  // --- MOCK DATA ---
  // In Phase 4, we will fetch these from FastAPI
  const mockEmergency = {
    id: 1,
    position: [32.0853, 34.7818],
    type: 'fire',
    severity: 'critical' // This applies the 'critical' CSS class (neon red breathing)
  };

  const mockVolunteer = {
    id: 101,
    position: [32.0700, 34.7700],
    status: 'dispatched' // This applies the 'dispatched' CSS class (neon cyan solid)
  };

  return (
    <MapContainer 
      center={centerPosition} 
      zoom={13} 
      style={{ height: '100%', width: '100%' }}
      zoomControl={false}
    >
      <MapResizer isLeftOpen={isLeftOpen} isRightOpen={isRightOpen} />
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
      />

      {/* Render the Active Emergency */}
      <Marker 
        position={mockEmergency.position} 
        icon={createEmergencyIcon(mockEmergency.severity, Flame)}
      />

      {/* Render the Volunteer */}
      <Marker 
        position={mockVolunteer.position} 
        icon={createVolunteerIcon(mockVolunteer.status)}
      />

      {/* Render Animated Route Line if volunteer is dispatched */}
      {mockVolunteer.status === 'dispatched' && (
        <Polyline 
          positions={[mockVolunteer.position, mockEmergency.position]} 
          color="var(--neon-cyan)" 
          weight={3}
          className="animated-route-line"
        />
      )}
    </MapContainer>
  );
};

export default MapComponent;
