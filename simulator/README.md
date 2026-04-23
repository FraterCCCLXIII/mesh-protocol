# HOLON Protocol Simulator

A simulation framework for testing and stress-testing the HOLON protocol at various scales.

## Purpose

- Validate protocol design decisions
- Find edge cases and performance bottlenecks
- Test scalability claims
- Demonstrate protocol behavior to stakeholders

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SCENARIO RUNNER                           │
│  Defines test scenarios, parameters, and success criteria   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    AGENT SYSTEM                              │
│  User agents with configurable behaviors                    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    CORE SIMULATOR                            │
│  In-memory implementation of Object/Structure/View layers   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    METRICS COLLECTOR                         │
│  Storage, latency, throughput, link counts                  │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
cd simulator
pip install -r requirements.txt
python run_simulation.py --scenario small_network
```

## Scenarios

| Scenario | Users | Holons | Duration | Focus |
|----------|-------|--------|----------|-------|
| `small_network` | 100 | 5 | 1 hour | Basic functionality |
| `medium_network` | 10,000 | 50 | 24 hours | Storage growth |
| `large_network` | 100,000 | 500 | 7 days | Scalability |
| `spam_attack` | 1,000 | 10 | 1 hour | Spam resistance |
| `viral_content` | 10,000 | 20 | 1 hour | Hot spots |
| `nested_holons` | 1,000 | 100 (deep) | 24 hours | Structure layer |
| `view_stress` | 10,000 | 50 | 1 hour | View layer |

## Metrics Collected

### Storage
- Total objects (entities, content, links)
- Storage size (bytes)
- Growth rate over time
- Link explosion tracking

### Performance
- Query latency (p50, p95, p99)
- View computation time
- Sync bandwidth

### Protocol-Specific
- Context stack depth distribution
- View verification success rate
- Key rotation overhead
- Fork detection events

## Output

Results are saved to `results/` with:
- `metrics.json` - Raw metrics data
- `summary.txt` - Human-readable summary
- `charts/` - Visualization PNGs
