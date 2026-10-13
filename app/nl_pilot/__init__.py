"""NL Real-Data Controlled Pilot.

GeoRisk Engine's first end-to-end execution against official Dutch
regulatory and geospatial source data.  Uses real BAG building data,
real Amsterdam Omgevingsplan source artifacts, and real KNMI/KNMI'23
scenario slices.

Architecture:
  Live acquisition → raw snapshot (SHA-256 sealed) → deterministic replay.
  CI replays sealed snapshots; live acquisition is opt-in.

Classification: This is a controlled pilot, NOT production-eligible.
All outputs are explicitly labelled as pilot evidence.
"""
