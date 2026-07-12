const API_BASE = 'http://127.0.0.1:8000/api/dashboard';

const getFallbackCoordinate = (id, baseLat = 32.085, baseLng = 34.781, spread = 0.05) => {
    const hash = (id * 2654435761) % 1000;
    const latOffset = ((hash % 100) / 100 - 0.5) * spread;
    const lngOffset = ((Math.floor(hash / 100) % 100) / 100 - 0.5) * spread;
    return [baseLat + latOffset, baseLng + lngOffset];
};

const arcgisQuery = async (query) => {
    const response = await fetch(`https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?f=json&singleLine=${encodeURIComponent(query)}&maxLocations=3`);
    const data = await response.json();
    return data.candidates || [];
};

const geocodeViaArcGIS = async (text, id) => {
    if (!text) return null;
    try {
        const cacheKey = `geo_v2_${text}`;
        const cached = localStorage.getItem(cacheKey);
        if (cached) return JSON.parse(cached);

        // Step 1: Clean conversational filler & generic adjectives
        let cleanText = text
            .replace(/\b(someone|please|send|help|now|happening|people|person|there's|there is|i see|i saw|we need)\b/ig, " ")
            .replace(/\b(near the|in the|next to|at the|inside the|outside the|around the|close to|by the|near|in|at|by)\b/ig, " ")
            .replace(/\b(big|small|large|main|huge)\b/ig, " ")
            .replace(/\s+/g, " ").trim();

        if (!cleanText) return null;

        // Step 2: First attempt — raw cleaned text
        let candidates = await arcgisQuery(cleanText);
        let best = candidates[0];

        // Step 3: If no good result OR result is suspiciously far from expected regions,
        // retry by extracting the most specific location words
        if (!best || best.score < 85) {
            // Try extracting just proper nouns / location-like words (capitalize pattern)
            const retryQuery = cleanText + ", Israel";
            const retryCandidates = await arcgisQuery(retryQuery);
            if (retryCandidates[0] && retryCandidates[0].score > (best?.score || 0)) {
                best = retryCandidates[0];
            }
        }

        if (best && best.score >= 60) {
            const coords = [best.location.y, best.location.x];
            localStorage.setItem(cacheKey, JSON.stringify(coords));
            return coords;
        }
    } catch (e) {
        console.error("ArcGIS fallback failed for", text, e);
    }
    return null;
};

export const fetchIncidents = async () => {
    try {
        const response = await fetch(`${API_BASE}/incidents`);
        if (!response.ok) throw new Error('Failed to fetch incidents');
        const data = await response.json();
        
        return await Promise.all(data.map(async inc => {
            let position;
            
            // 1. Use backend-evaluated coordinates (from Location Evaluator)
            if (inc.latitude && inc.longitude) {
                position = [inc.latitude, inc.longitude];
            } 
            // 2. Fallback: geocode via ArcGIS on frontend for existing incidents without coords
            else {
                const geocoded = await geocodeViaArcGIS(inc.location_text, inc.id);
                position = geocoded || getFallbackCoordinate(inc.id, 32.07, 34.78, 0.05);
            }

            return {
                ...inc,
                type: inc.incident_type || 'unknown',
                time: new Date(inc.created_at).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
                message: inc.raw_text,
                locationName: inc.location_text || "Unknown Location",
                contactName: inc.contact_name || "Unknown",
                phone: inc.phone_number,
                aiConfidence: inc.confidence !== undefined ? Math.round(inc.confidence * 100) : 0,
                requiredEquipment: inc.needs || [],
                aiSynthesis: inc.summary || "Pending Analysis...",
                siteAccessibility: inc.metadata_json?.siteAccessibility || "Unknown",
                position,
                timeline: inc.metadata_json?.timeline || [] 
            };
        }));
    } catch (e) {
        console.error("fetchIncidents error:", e);
        return [];
    }
};

export const fetchVolunteers = async () => {
    try {
        const response = await fetch(`${API_BASE}/volunteers`);
        if (!response.ok) throw new Error('Failed to fetch volunteers');
        const data = await response.json();
        
        return await Promise.all(data.map(async vol => {
            const geocoded = await geocodeViaArcGIS(vol.metadata_json?.location_text || "", vol.id);
            const position = geocoded || getFallbackCoordinate(vol.id, 32.07, 34.78, 0.08);
            return {
                ...vol,
                position,
                skills: vol.metadata_json?.skills || [],
                vehicle: vol.metadata_json?.vehicle || "Unknown",
                distance: vol.metadata_json?.distance || "0km",
                role: vol.metadata_json?.role || "General Responder",
                username: vol.source_username,
                phone: vol.metadata_json?.phone_number,
                assignedIncidentId: vol.assigned_incident_id || null,
                dispatchStatus: vol.dispatch_status || null,
                lastSeen: vol.last_seen_at ? new Date(vol.last_seen_at).toLocaleString('he-IL', { dateStyle: 'short', timeStyle: 'short' }) : "Unknown"
            };
        }));
    } catch (e) {
        console.error("fetchVolunteers error:", e);
        return [];
    }
};

export const fetchAssignments = async () => {
    try {
        const response = await fetch(`${API_BASE}/assignments`);
        if (!response.ok) return [];
        return await response.json();
    } catch (e) {
        console.error("fetchAssignments error:", e);
        return [];
    }
};

export const dispatchVolunteer = async (volunteerId, incidentId) => {
    console.log(`Simulating dispatch for Vol:${volunteerId} -> Inc:${incidentId}`);
    return { success: true };
};

export const fetchRecommendations = async (incidentId) => {
    try {
        const response = await fetch(`http://127.0.0.1:8000/dispatch/incidents/${incidentId}/recommendations`);
        if (!response.ok) return [];
        return await response.json();
    } catch (e) {
        console.error("fetchRecommendations error:", e);
        return [];
    }
};
