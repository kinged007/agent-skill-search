---
name: api-design
description: "Design RESTful and GraphQL APIs: resource modeling, versioning strategies, pagination, error handling, rate limiting, and OpenAPI spec generation."
metadata:
  hermes:
    category: backend
---

# API Design

## When to Use
When designing new endpoints, reviewing API contracts, or restructuring existing APIs.

## Procedure
1. Define resources and their relationships
2. Choose REST (resource-oriented) or GraphQL (client-driven) based on needs
3. Design URL structure: /resource/{id}/sub-resource
4. Implement consistent error responses with proper HTTP status codes
5. Add pagination (cursor-based preferred over offset)
6. Generate OpenAPI/Swagger spec for documentation
