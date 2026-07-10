import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Polyline, useMap, useMapEvents, Popup } from 'react-leaflet';
import VolunteerCard from './components/VolunteerCard';
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

// A component to track zoom level and update state
const ZoomTracker = ({ onZoomChange }) => {
  useMapEvents({
    zoomend: (e) => {
      onZoomChange(e.target.getZoom());
    }
  });
  return null;
};

// Component to fly to the selected volunteer
const FlyToVolunteer = ({ selectedVolunteer }) => {
  const map = useMap();
  useEffect(() => {
    if (selectedVolunteer) {
      map.flyTo(selectedVolunteer.position, 16, {
        duration: 1.5,
        easeLinearity: 0.25,
      });
    }
  }, [selectedVolunteer, map]);
  return null;
};

// Create custom Emergency Icon with dynamic sizing
const createEmergencyIcon = (severity, IconComponent, zoom) => {
  let size = 32;
  let iconSize = 18;
  
  if (zoom <= 11) { size = 12; iconSize = 0; }
  else if (zoom === 12) { size = 16; iconSize = 0; }
  else if (zoom === 13) { size = 24; iconSize = 14; }

  const markerHtml = iconSize > 0 
    ? renderToString(
        <div className={`emergency-marker ${severity}`} style={{ width: `${size}px`, height: `${size}px` }}>
          <IconComponent size={iconSize} strokeWidth={1.5} color="white" />
        </div>
      )
    : `<div class="emergency-marker ${severity}" style="width: ${size}px; height: ${size}px;"></div>`;

  return L.divIcon({
    className: 'custom-icon-wrapper',
    html: markerHtml,
    iconSize: [size, size],
    iconAnchor: [size/2, size/2],
  });
};

// Create custom Volunteer Icon with dynamic sizing
const createVolunteerIcon = (statusClass, zoom) => {
  let size = 12;
  if (zoom <= 11) size = 4;
  else if (zoom <= 13) size = 8;

  return L.divIcon({
    className: 'custom-icon-wrapper',
    html: `<div class="volunteer-marker ${statusClass}" style="width: ${size}px; height: ${size}px;"></div>`,
    iconSize: [size, size],
    iconAnchor: [size/2, size/2],
  });
};

const MapComponent = ({ isLeftOpen, isRightOpen, incidents = [], volunteers = [], selectedVolunteer, onVolunteerClick, onIncidentClick }) => {
  const [zoomLevel, setZoomLevel] = useState(14);
  const centerPosition = [32.0653, 34.7750]; // Slightly adjusted for better view of all incidents

  return (
    <MapContainer
      center={centerPosition}
      zoom={zoomLevel}
      style={{ height: '100%', width: '100%' }}
      zoomControl={false}
    >
      <MapResizer isLeftOpen={isLeftOpen} isRightOpen={isRightOpen} />
      <ZoomTracker onZoomChange={setZoomLevel} />
      <FlyToVolunteer selectedVolunteer={selectedVolunteer} />
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
      />

      {/* Render Incidents */}
      {incidents.map(inc => (
        <Marker
          key={`inc-${inc.id}`}
          position={inc.position}
          icon={createEmergencyIcon(inc.severity, inc.type === 'fire' ? AlertTriangle : inc.type === 'medical' ? Activity : ShieldAlert, zoomLevel)}
          eventHandlers={{
            click: () => {
              if (onIncidentClick) onIncidentClick(inc);
            }
          }}
        />
      ))}

      {/* Render Volunteers */}
      {volunteers.map(vol => (
        <Marker 
          key={`vol-${vol.id}`}
          position={vol.position} 
          icon={createVolunteerIcon(vol.status, zoomLevel)}
          eventHandlers={{
            click: () => {
              if (onVolunteerClick) onVolunteerClick(vol);
            }
          }}
        >
          <Popup className="tactical-popup" minWidth={250} closeButton={false}>
            <VolunteerCard volunteer={vol} />
          </Popup>
        </Marker>
      ))}

      {/* Render Animated Route Lines for dispatched volunteers */}
      {volunteers.filter(v => (v.status === 'dispatched' || v.status === 'en_route') && v.assignedTo).map(vol => {
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
