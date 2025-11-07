# India Road Trip Planner

A smart, India-specific road trip planning web application that helps you plan your perfect road trip with optimized routes, smart stops, and cost estimates.

## Features

- 🗺️ Interactive Route Planning
- ⛽ Fuel Cost Estimation
- 🏨 Smart Hotel Suggestions
- 🍽️ Restaurant Recommendations
- 🛣️ Toll Cost Calculation
- 🕒 Time-Aware Stop Planning
- 🚗 Vehicle Profile Management
- 📱 Mobile-Friendly Interface

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd roadtrip_planner
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file in the root directory with the following keys:

```
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
TOLLGURU_API_KEY=your_tollguru_api_key
GEMINI_API_KEY=your_gemini_api_key
```

## Directory Structure

```
roadtrip_planner_v2/
├── app.py
├── requirements.txt
├── README.md
├── documentation.txt
├── utils/
│   ├── maps.py
│   ├── places.py
│   ├── tolls.py
│   ├── llm.py
│   ├── fuel.py
│   ├── profiles.py
│   ├── schedule.py
│   ├── auth.py
│   ├── trip_planner.py
│   └── __init__.py
├── users/
├── profiles/
│   ├── vehicles/
│   └── users/
```

## Additional Dependencies

- `pydeck` for map visualizations
- `googlemaps` for Google Maps API
- `google-generativeai` for Gemini LLM
- `python-dotenv` for environment variable management
- `requests`, `flask`, `geopy`, `polyline`, `beautifulsoup4`, `openai`

## .gitignore Recommendation

Create a `.gitignore` file with at least the following:

```
.env
__pycache__/
*.pyc
users/*.json
profiles/users/*.json
profiles/vehicles/*.json
```

Do **not** commit your `.env` file or any files containing secrets or user data.

## API Keys Required

- Google Maps API Key (with the following APIs enabled):
  - Maps JavaScript API
  - Directions API
  - Places API
  - Distance Matrix API
  - Geocoding API

## Usage

1. Enter your starting point and destination
2. Select your vehicle type and profile
3. Set your preferred driving hours and meal times
4. Get your optimized route with:
   - Distance and duration
   - Fuel cost estimation
   - Suggested stops for meals and rest
   - Hotel recommendations for overnight stays
   - Toll cost calculation

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

 
