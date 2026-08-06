# Phase 6 – Live map

## What it looks like

Google Maps–style navigation UI using **Leaflet** + **CARTO Voyager** tiles (OpenStreetMap data — not the Google Maps API).

On an active journey you get:

- Full-bleed street map
- Blue pulsing “you are here” marker + accuracy circle
- Blue path polyline of uploaded GPS points
- Green start marker
- Red destination pin (if dest lat/lng provided)
- Follow-me camera
- Floating SOS + Pause / End controls over the map

## Try it

1. Add a contact
2. Open **Journey**
3. Enter destination; optionally expand **destination coordinates** for a red pin
4. Start journey and allow GPS

## Note for viva

SafeRoute uses free OSM/CARTO tiles. It is **not** Google Maps and does not replace Google navigation.
