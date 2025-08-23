# Backend Implementation Tasks

This document outlines the tasks required to build the backend system, including the orchestrator and AI agents.

## Progress Tracker

### Phase 1: Core Services Setup

- [ ] **Orchestrator**: Set up the initial Next.js API route for the orchestrator (`/api/query`).
- [ ] **Geospatial Agent**: Refactor `app.py` into a Dockerized Flask/FastAPI microservice.
- [ ] **Communication**: Implement basic request forwarding from the orchestrator to the Geospatial Agent.

### Phase 2: Agent Development & Integration

- [ ] **Socioeconomic Agent**: Develop the microservice to fetch and process census and economic data.
- [ ] **Real Estate Agent**: Develop the microservice for real estate market analysis and prediction.
- [ ] **Environmental Agent**: Develop the microservice for environmental data analysis.
- [ ] **Integration**: Connect all agents to the orchestrator.

### Phase 3: Advanced Orchestration

- [ ] **NLU**: Implement Natural Language Understanding to parse user queries into structured commands.
- [ ] **Task Dispatching**: Implement logic to call the relevant agents in parallel based on the parsed query.
- [ ] **Aggregation & Synthesis**: Implement logic to aggregate results and generate a coherent narrative summary.
- [ ] **Caching**: Implement a caching layer (e.g., Redis) for query responses.

### Phase 4: Data Storage & Deployment

- [ ] **Database**: Set up PostgreSQL with PostGIS for storing structured and geospatial data.
- [ ] **Object Storage**: Set up an S3-compatible solution for storing satellite imagery and model artifacts.
- [ ] **Deployment**: Create Kubernetes configurations for deploying the entire backend system.

## API Endpoint Definitions

### 1. Orchestrator API

The orchestrator provides the primary entry point for the frontend.

- **Endpoint**: `POST /api/query`

  - **Description**: Accepts a natural language query from the user, initiates an asynchronous analysis task, and returns a task ID.
  - **Request Body**:
    ```json
    {
      "query": "Show urban growth and predict real estate prices in Dubai since 2020"
    }
    ```
  - **Success Response (202 Accepted)**:
    ```json
    {
      "taskId": "a1b2c3d4-e5f6-7890-g1h2-i3j4k5l6m7n8"
    }
    ```

- **Endpoint**: `GET /api/results/{taskId}`
  - **Description**: Polls for the result of an analysis task.
  - **Success Response (200 OK)**:
    - **If pending**:
      ```json
      {
        "status": "processing"
      }
      ```
    - **If complete**:
      ```json
      {
        "status": "complete",
        "narrativeSummary": "Dubai has seen a 15% increase in urban areas since 2020... Real estate prices are projected to rise by 8% in the next year.",
        "results": {
          "geospatial": {
            /* ... data from Geospatial Agent ... */
          },
          "real_estate": {
            /* ... data from Real Estate Agent ... */
          }
        }
      }
      ```

### 2. AI Agent APIs

All agents follow a consistent API design.

- **Endpoint**: `POST /analyze`
  - **Description**: Executes a specific analysis for a given location and parameters.
  - **Example Request (Geospatial Agent)**:
    ```json
    {
      "location": { "lat": 25.2048, "lon": 55.2708 },
      "time_range": { "start": "2020-01-01", "end": "2023-12-31" },
      "analysis_type": "urban_change"
    }
    ```
  - **Example Request (Real Estate Agent)**:
    ```json
    {
      "location": { "city": "Dubai", "country": "UAE" },
      "prediction_horizon": "1_year"
    }
    ```
  - **Success Response (200 OK)**:
    - Returns a JSON object with the analysis results, specific to the agent's function.
    ```json
    {
      "status": "success",
      "data": {
        /* ... agent-specific results ... */
      }
    }
    ```
