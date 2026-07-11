export const MOCK_INCIDENTS = [
    {
      id: 1,
      type: 'fire',
      severity: 'critical',
      siteAccessibility: 'Underground (Restricted)',
      aiConfidence: 96,
      casualties: 'Unknown (High Potential)',
      requiredEquipment: ['Burn Kits', 'Oxygen', 'Fire Extinguishers'],
      time: '14:32',
      message: 'Help! There is a huge fire in the Dizengoff Center tunnel, people are trapped!',
      locationName: 'Dizengoff Center, TLV',
      position: [32.0779, 34.7744],
      aiSynthesis: "Report analyzed: Large-scale fire in an enclosed public space (Dizengoff Center tunnel). Due to reports of trapped individuals, urgency is elevated to CRITICAL. Action taken: Dispatched 3 motorcycle-based paramedics, in order to bypass anticipated heavy traffic.",
      timeline: [
        { time: '14:32', event: 'Received distress WhatsApp message.', active: false },
        { time: '14:32', event: 'AI parsed location and assessed CRITICAL severity.', active: false },
        { time: '14:33', event: 'AI automatically dispatched 3 nearest riders.', active: false },
        { time: '14:34', event: '2 Volunteers confirmed En Route.', active: true }
      ]
    },
    {
      id: 2,
      type: 'medical',
      severity: 'high',
      siteAccessibility: 'Open Street (Traffic)',
      aiConfidence: 99,
      casualties: '1 (Unconscious)',
      requiredEquipment: ['Defibrillator (AED)', 'BLS Kit'],
      time: '14:30',
      message: 'Someone collapsed on the street, not breathing, send help fast.',
      locationName: 'Rothschild Blvd 22, TLV',
      position: [32.0617, 34.7711],
      aiSynthesis: "Report analyzed: Unconscious, non-breathing individual on the street. Diagnosis: Suspected cardiac arrest. Action taken: Dispatched nearest available volunteers equipped with AEDs, for immediate resuscitation.",
      timeline: [
        { time: '14:30', event: 'Received emergency report.', active: false },
        { time: '14:31', event: 'AI identified cardiac arrest indicators.', active: false },
        { time: '14:31', event: 'Dispatched 2 volunteers with AEDs.', active: false },
        { time: '14:35', event: 'Volunteer arrived On Scene.', active: true }
      ]
    },
    {
      id: 3,
      type: 'security',
      severity: 'medium',
      siteAccessibility: 'Crowded Hub',
      aiConfidence: 82,
      casualties: 'None',
      requiredEquipment: ['Radio', 'Observation Kit'],
      time: '14:15',
      message: 'Suspicious object found near the bus station, please check.',
      locationName: 'Central Bus Station, TLV',
      position: [32.0560, 34.7795],
      aiSynthesis: "Report analyzed: Suspicious object located in a high-traffic transit hub. Action taken: Dispatched reconnaissance volunteer for visual verification, prior to bomb squad escalation.",
      timeline: [
        { time: '14:15', event: 'Received suspicious object report.', active: false },
        { time: '14:16', event: 'AI dispatched 1 reconnaissance volunteer.', active: false },
        { time: '14:20', event: 'Volunteer is On Scene, investigating.', active: true }
      ]
    }
];

export const MOCK_VOLUNTEERS = [
    { 
      id: 101, position: [32.0620, 34.7700], status: 'available', assignedTo: null, name: 'Yossi Cohen', role: 'Paramedic', distance: '1.2 km',
      gender: 'Male', height: '1.82m', weight: '85kg', trustScore: '98%', incidentsHandled: 142,
      equipment: ['Advanced Paramedic Bag', 'Defibrillator'], vehicle: 'Motorcycle 600cc', skills: ['ALS', 'Trauma']
    },
    { 
      id: 102, position: [32.0650, 34.7650], status: 'available', assignedTo: null, name: 'Yael Levi', role: 'Rider', distance: '0.5 km',
      gender: 'Female', height: '1.65m', weight: '60kg', trustScore: '95%', incidentsHandled: 15,
      equipment: ['BLS Bag', 'Bandages'], vehicle: 'Scooter 125cc', skills: ['Basic First Aid', 'Fast Navigation']
    },
    { 
      id: 103, position: [32.0580, 34.7750], status: 'on_scene', assignedTo: 2, name: 'Avi Yitzhak', role: 'Driver', distance: '1.2 km',
      gender: 'Male', height: '1.78m', weight: '90kg', trustScore: '88%', incidentsHandled: 120,
      equipment: ['BLS Bag', 'Stretcher'], vehicle: 'Ambulance', skills: ['Emergency Driving', 'ALS Assist']
    },
    { 
      id: 104, position: [32.0800, 34.7850], status: 'waiting', assignedTo: 1, name: 'Sarah Aharon', role: 'Paramedic', distance: '4.0 km',
      gender: 'Female', height: '1.70m', weight: '65kg', trustScore: '100%', incidentsHandled: 8,
      equipment: ['Full Paramedic Bag'], vehicle: 'Private Car (SUV)', skills: ['Pediatric Care', 'Trauma']
    },
    { 
      id: 105, position: [32.0500, 34.7700], status: 'available', assignedTo: null, name: 'Moshe Ben-David', role: 'Rider', distance: '3.3 km',
      gender: 'Male', height: '1.75m', weight: '78kg', trustScore: '92%', incidentsHandled: 27,
      equipment: ['BLS Bag', 'Burns Kit'], vehicle: 'Motorcycle 500cc', skills: ['Basic First Aid']
    },
    { 
      id: 106, position: [32.0880, 34.7750], status: 'en_route', assignedTo: 1, name: 'Maya Golan', role: 'Rider', distance: '5.1 km',
      gender: 'Female', height: '1.68m', weight: '62kg', trustScore: '96%', incidentsHandled: 34,
      equipment: ['First Responder Bag'], vehicle: 'Scooter 250cc', skills: ['Basic First Aid', 'Search & Rescue']
    },
    { 
      id: 107, position: [32.0710, 34.7850], status: 'available', assignedTo: null, name: 'Ronit Schwartz', role: 'Paramedic', distance: '1.8 km',
      gender: 'Female', height: '1.72m', weight: '68kg', trustScore: '98%', incidentsHandled: 89,
      equipment: ['Advanced Paramedic Bag', 'Intubation Kit'], vehicle: 'Private Car', skills: ['ALS', 'Toxicology']
    },
    { 
      id: 108, position: [32.0590, 34.7600], status: 'waiting', assignedTo: 2, name: 'Eli Malka', role: 'Rider', distance: '0.9 km',
      gender: 'Male', height: '1.85m', weight: '88kg', trustScore: '90%', incidentsHandled: 12,
      equipment: ['BLS Bag'], vehicle: 'Motorcycle 300cc', skills: ['Basic First Aid']
    },
    { 
      id: 109, position: [32.0450, 34.7550], status: 'available', assignedTo: null, name: 'Tamar Edri', role: 'Paramedic', distance: '3.5 km',
      gender: 'Female', height: '1.60m', weight: '55kg', trustScore: '100%', incidentsHandled: 4,
      equipment: ['Trauma Kit', 'Defibrillator'], vehicle: 'Ambulance', skills: ['ALS', 'Pediatric Care']
    },
    { 
      id: 110, position: [32.0620, 34.7800], status: 'on_scene', assignedTo: 3, name: 'Idan Levy', role: 'Driver', distance: '1.5 km',
      gender: 'Male', height: '1.76m', weight: '80kg', trustScore: '94%', incidentsHandled: 55,
      equipment: ['BLS Bag'], vehicle: 'Ambulance', skills: ['Emergency Driving']
    },
    { 
      id: 111, position: [32.0950, 34.7820], status: 'available', assignedTo: null, name: 'Omer Gershon', role: 'Rider', distance: '6.2 km',
      gender: 'Male', height: '1.80m', weight: '75kg', trustScore: '99%', incidentsHandled: 210,
      equipment: ['First Responder Bag'], vehicle: 'Motorcycle 600cc', skills: ['Basic First Aid']
    }
];
