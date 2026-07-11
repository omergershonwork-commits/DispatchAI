import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Polyline, useMap, useMapEvents, Popup, Tooltip } from 'react-leaflet';
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

// Component to handle camera movements
const MapCameraHandler = ({ selectedVolunteer, selectedIncident, leftTab, volunteers, incidents }) => {
  const map = useMap();
  const prevVol = React.useRef(selectedVolunteer?.id);
  const prevInc = React.useRef(selectedIncident?.id);

  useEffect(() => {
    const volChanged = selectedVolunteer?.id !== prevVol.current;
    const incChanged = selectedIncident?.id !== prevInc.current;
    
    prevVol.current = selectedVolunteer?.id;
    prevInc.current = selectedIncident?.id;
    
    if (!volChanged && !incChanged) return;

    if (leftTab === 'incidents' && selectedIncident) {
      if (selectedVolunteer) {
        const bounds = L.latLngBounds([selectedVolunteer.position, selectedIncident.position]);
        map.flyToBounds(bounds, { padding: [50, 50], duration: 1.5 });
      } else {
        const assignedVols = volunteers.filter(v => v.assignedTo === selectedIncident.id);
        if (assignedVols.length > 0) {
          const bounds = L.latLngBounds([selectedIncident.position, ...assignedVols.map(v => v.position)]);
          map.flyToBounds(bounds, { padding: [80, 80], duration: 1.5 });
        } else {
          map.flyTo(selectedIncident.position, 15, { duration: 1.5, easeLinearity: 0.25 });
        }
      }
    } else if (leftTab === 'forces' && selectedVolunteer) {
      if (selectedVolunteer.assignedTo && incidents) {
        const assignedIncident = incidents.find(i => i.id === selectedVolunteer.assignedTo);
        if (assignedIncident) {
          const bounds = L.latLngBounds([selectedVolunteer.position, assignedIncident.position]);
          map.flyToBounds(bounds, { padding: [50, 50], duration: 1.5 });
          return;
        }
      }
      map.flyTo(selectedVolunteer.position, 16, { duration: 1.5, easeLinearity: 0.25 });
    }
  }, [selectedVolunteer, selectedIncident, leftTab, map, volunteers, incidents]);
  return null;
};

// Create custom Emergency Icon with dynamic sizing
const createEmergencyIcon = (severity, IconComponent, zoom, isSelected) => {
  let size = 32;
  let iconSize = 18;
  
  if (zoom <= 9) { size = 12; iconSize = 0; }
  else if (zoom <= 11) { size = 20; iconSize = 12; }
  else if (zoom === 12) { size = 24; iconSize = 14; }

  const markerHtml = iconSize > 0 
    ? renderToString(
        <div className={`emergency-marker ${severity} ${isSelected ? 'selected' : ''}`} style={{ width: `${size}px`, height: `${size}px` }}>
          <IconComponent size={iconSize} strokeWidth={1.5} color="white" />
        </div>
      )
    : `<div class="emergency-marker ${severity} ${isSelected ? 'selected' : ''}" style="width: ${size}px; height: ${size}px;"></div>`;

  return L.divIcon({
    className: 'custom-icon-wrapper',
    html: markerHtml,
    iconSize: [size, size],
    iconAnchor: [size/2, size/2],
  });
};

// Create custom Volunteer Icon with dynamic sizing
const createVolunteerIcon = (statusClass, zoom, isSelected) => {
  let size = 12;
  if (zoom <= 11) size = 4;
  else if (zoom <= 13) size = 8;
  
  return L.divIcon({
    className: 'custom-icon-wrapper',
    html: `<div class="volunteer-marker ${statusClass} ${isSelected ? 'selected' : ''}" style="width: ${size}px; height: ${size}px;"></div>`,
    iconSize: [size, size],
    iconAnchor: [size/2, size/2],
  });
};

const MapComponent = ({ isLeftOpen, isRightOpen, incidents = [], volunteers = [], selectedVolunteer, selectedIncident, leftTab, onVolunteerClick, onIncidentClick }) => {
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
      <MapCameraHandler selectedVolunteer={selectedVolunteer} selectedIncident={selectedIncident} leftTab={leftTab} volunteers={volunteers} incidents={incidents} />
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
      />

      {/* Render Incidents (Emergencies) */}
      {incidents.map(incident => (
        <Marker 
          key={`inc-${incident.id}`}
          position={incident.position} 
          icon={createEmergencyIcon(incident.severity, incident.type === 'fire' ? AlertTriangle : incident.type === 'medical' ? Activity : ShieldAlert, zoomLevel, selectedIncident?.id === incident.id)}
          eventHandlers={{
            click: () => {
              if (onIncidentClick) onIncidentClick(incident);
            }
          }}
        />
      ))}

      {/* Render Volunteers */}
      {volunteers.map(vol => (
        <Marker 
          key={vol.id} 
          position={vol.position} 
          icon={createVolunteerIcon(vol.status, zoomLevel, selectedVolunteer?.id === vol.id)}
          eventHandlers={{
            click: () => {
              if (onVolunteerClick) onVolunteerClick(vol);
            }
          }}
        >
          <Tooltip direction="top" offset={[0, -20]} opacity={1} className="volunteer-tooltip">
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ 
                width: '6px', 
                height: '6px', 
                borderRadius: '50%', 
                backgroundColor: vol.status === 'available' ? '#10b981' : '#f59e0b',
                boxShadow: `0 0 4px ${vol.status === 'available' ? '#10b981' : '#f59e0b'}`
              }} />
              <span style={{ fontWeight: 500, fontSize: '0.8rem', letterSpacing: '0.5px' }}>
                {vol.name}
              </span>
            </div>
          </Tooltip>
        </Marker>
      ))}

      {/* Render Animated Route Lines for dispatched volunteers */}
      {volunteers.filter(v => (v.status === 'dispatched' || v.status === 'en_route') && v.assignedTo).map(vol => {
        const targetIncident = incidents.find(i => i.id === vol.assignedTo);
        if (!targetIncident) return null;
        return (
          <React.Fragment key={`route-${vol.id}`}>
            <Polyline
              positions={[vol.position, targetIncident.position]}
              color="var(--tactical-blue)"
              weight={2}
              className="route-line-bg"
            />
            <Polyline
              positions={[vol.position, targetIncident.position]}
              color="var(--tactical-blue)"
              weight={2}
              className="animated-route-line"
            />
          </React.Fragment>
        );
      })}
    </MapContainer>
  );
};

export default MapComponent;
