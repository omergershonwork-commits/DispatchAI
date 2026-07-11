import { MOCK_INCIDENTS, MOCK_VOLUNTEERS } from './mockData';

// In-memory state so we can mutate it when dispatching
let currentIncidents = [...MOCK_INCIDENTS];
let currentVolunteers = [...MOCK_VOLUNTEERS];

const simulateNetworkDelay = (ms = 300) => new Promise(resolve => setTimeout(resolve, ms));

export const fetchIncidents = async () => {
    await simulateNetworkDelay();
    return [...currentIncidents];
};

export const fetchVolunteers = async () => {
    await simulateNetworkDelay();
    return [...currentVolunteers];
};

export const dispatchVolunteer = async (volunteerId, incidentId) => {
    await simulateNetworkDelay(500);
    
    // Update volunteer status
    currentVolunteers = currentVolunteers.map(v => 
        v.id === volunteerId 
            ? { ...v, status: 'dispatched', assignedTo: incidentId } 
            : v
    );

    // Optionally update incident timeline
    const volunteerName = currentVolunteers.find(v => v.id === volunteerId)?.name || "Volunteer";
    currentIncidents = currentIncidents.map(inc => {
        if (inc.id === incidentId) {
            const newTimeline = [...inc.timeline];
            // Mark previous active as inactive
            if (newTimeline.length > 0) {
                newTimeline[newTimeline.length - 1].active = false;
            }
            newTimeline.push({
                time: new Date().toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
                event: `Manual Override: Dispatched ${volunteerName}`,
                active: true
            });
            return { ...inc, timeline: newTimeline };
        }
        return inc;
    });

    return { success: true };
};
