import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Polyline, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { renderToString } from 'react-dom/server';
import { AlertTriangle, ShieldAlert, Activity } from 'lucide-react';

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
const createEmergencyIcon = (severity, IconComponent) => {
  return L.divIcon({
    className: 'custom-icon-wrapper',
    html: renderToString(
      <div className={`emergency-marker ${severity}`}>
        <IconComponent size={16} strokeWidth={1.5} color="white" />
      </div>
    ),
    iconSize: [28, 28],
    iconAnchor: [14, 14],
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

const MapComponent = ({ isLeftOpen, isRightOpen, incidents = [], volunteers = [] }) => {
  // Center of Tel Aviv
  const centerPosition = [32.0653, 34.7750]; // Slightly adjusted for better view of all incidents

  return (
    <MapContainer 
      center={centerPosition} 
      zoom={14} 
      style={{ height: '100%', width: '100%' }}
      zoomControl={false}
    >
      <MapResizer isLeftOpen={isLeftOpen} isRightOpen={isRightOpen} />
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
      />

      {/* Render Incidents */}
      {incidents.map(inc => (
        <Marker 
          key={`inc-${inc.id}`}
          position={inc.position} 
          icon={createEmergencyIcon(inc.severity, inc.type === 'fire' ? AlertTriangle : inc.type === 'medical' ? Activity : ShieldAlert)}
        />
      ))}

      {/* Render Volunteers */}
      {volunteers.map(vol => (
        <Marker 
          key={`vol-${vol.id}`}
          position={vol.position} 
          icon={createVolunteerIcon(vol.status)}
        />
      ))}

      {/* Render Animated Route Lines for dispatched volunteers */}
      {volunteers.filter(v => v.status === 'dispatched' && v.assignedTo).map(vol => {
        const targetIncident = incidents.find(i => i.id === vol.assignedTo);
        if (!targetIncident) return null;
        return (
          <Polyline 
            key={`route-${vol.id}`}
            positions={[vol.position, targetIncident.position]} 
            color="var(--tactical-blue)" 
            weight={2}
            className="animated-route-line"
          />
        );
      })}
    </MapContainer>
  );
};

export default MapComponent;
