---
name: monitoring
description: "Set up application monitoring with Prometheus and Grafana: metrics collection, alerting rules, dashboards, and SLI/SLO tracking."
metadata:
  hermes:
    category: observability
---

# Application Monitoring

## When to Use
When setting up observability, creating dashboards, or configuring alerts.

## Procedure
1. Instrument code with Prometheus metrics (counters, histograms, gauges)
2. Create Prometheus scrape configs
3. Build Grafana dashboards for key metrics
4. Define alerting rules for SLI breaches
5. Set up PagerDuty/OpsGenie integration for critical alerts
