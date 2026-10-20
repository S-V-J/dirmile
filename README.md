# Dirmile

Dirmile is a full-stack web application that helps truck drivers choose safer routes based on weather conditions, load weight, and estimated travel time.

The driver enters:

- Origin
- Destination
- Departure date and time
- Load weight in pounds
- Weather checkpoint interval: 10, 25, or 50 miles

Dirmile then:

- Generates up to 3 route options using a routing API
- Estimates arrival time at each checkpoint
- Samples weather at each checkpoint using the estimated arrival time
- Classifies weather risk using defined wind, rain, and snow thresholds
- Applies truck load-based risk overrides
- Recommends the safest practical route
- Shows routes, checkpoints, ETAs, risk levels, and summaries on a map
- Shows a weather heatmap along the trip corridor with a 0–48 hour forecast slider

## Application Name

**Dirmile**

## Target Repository

```text
git@github.com:S-V-J/dirmile.git
```

## Planned Stack

### Backend

- Python
- Django
- Django REST Framework
- SQLite for development
- Open-Meteo weather API
- OSRM routing API
- Open-Meteo geocoding API

### Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- Leaflet
- Leaflet.heat
- PWA support

### Hosting

- WSL Linux
- Django backend
- Built React frontend served as static files
- Cloudflare Tunnel for free public HTTPS access

## Project Structure

```text
/home/ML/dirmile
├── Backend/
├── Frontend/
├── README.md
├── .gitignore
└── LICENSE
```

## Current Status

This repository is in the initial setup phase.

The next phases will add:

1. Django backend foundation
2. Authentication and account management
3. Routing, geocoding, and weather integrations
4. Risk calculation engine
5. Route recommendation logic
6. React frontend
7. Map and heatmap UI
8. PWA installation support
9. Cloudflare Tunnel hosting
10. Testing, documentation, and final deployment

## License

Dirmile is released under the MIT License. See the `LICENSE` file for details.
