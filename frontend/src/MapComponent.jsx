import React, { useEffect } from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css'; // Essential for Leaflet to render correctly

// Helper component to force Leaflet to recalculate its size after CSS transitions finish
const MapResizer = ({ isLeftOpen, isRightOpen }) => {
  const map = useMap();

  useEffect(() => {
    // The CSS transition takes 0.3s (300ms), so we wait 350ms to be safe, then tell the map to recalculate
    const timeout = setTimeout(() => {
      map.invalidateSize();
    }, 350);
    
    return () => clearTimeout(timeout);
  }, [isLeftOpen, isRightOpen, map]);

  return null;
};

const MapComponent = ({ isLeftOpen, isRightOpen }) => {
  // Center of Tel Aviv for our Hackathon Demo starting point
  const centerPosition = [32.0853, 34.7818];

  return (
    <MapContainer 
      center={centerPosition} 
      zoom={13} 
      style={{ height: '100%', width: '100%' }}
      zoomControl={false} // Hidden for a cleaner, modern look
    >
      <MapResizer isLeftOpen={isLeftOpen} isRightOpen={isRightOpen} />
      <TileLayer
        // CartoDB Dark Matter tile layer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
      />
    </MapContainer>
  );
};

export default MapComponent;
