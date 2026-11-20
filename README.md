# GNSS Network Planner

## Overview

A Python-based tool for GNSS monitoring network planning and satellite visibility analysis.

The project supports multi-GNSS satellite orbit computation and visibility assessment using:

- GPS
- Galileo
- BeiDou
- GLONASS


---

## Features

### Satellite Visibility Analysis

- Elevation and azimuth computation
- Visibility statistics
- Coverage assessment on geographic grids


### Almanac Processing

Supported sources:

- u-blox UBX Almanac messages
- u-blox AssistNow Multi-GNSS Almanac downloads
- Future support for additional almanac formats

### Broadcast Ephemeris Processing

- RINEX Navigation files
- Multi-GNSS broadcast ephemerides

### Network Planning

- Visibility analysis for existing stations
- Coverage-gap identification

---

## Supported Input Data

### Almanac Sources

- u-blox AssistNow MGA messages
- u-blox Almanac messages

### Navigation Data

- RINEX Navigation files
- Multi-GNSS broadcast ephemerides

---

## Current Development Focus

- Multi-GNSS almanac support
- AssistNow integration
- Broadcast ephemeris processing
- Coverage-gap analysis
- GNSS monitoring network optimisation

---

## Development Status

The project is under active development. Interfaces, file formats, and internal APIs may change between releases.

---

## License

```text
Apache License 2.0
```

---

## Authors

- Bence Takács
- Márton Farkas