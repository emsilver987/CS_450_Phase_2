# ACME Registry API - OpenAPI Specification

This document contains all API endpoints in OpenAPI 3.0.2 specification format.

## OpenAPI Specification

```yaml
openapi: 3.0.2
info:
  title: ACME Registry API
  version: 3.4.4
  description: |
    API for ECE 461/Fall 2025/Project Phase 2: A Trustworthy Model Registry
    
    All endpoints have BASELINE or NON-BASELINE listed. Please read through all descriptions before raising questions.
    
    An `artifact_id` is a unique identifier for each model/dataset/code entry. (Key idea -> the id is unique for all entities, even when a source reuses the same name).
    
    Hugging Face models rarely expose formal revision tags, so treat every ingest as a standalone artifact identified solely by its name and generated id.
  termsOfService: http://swagger.io/terms/
  contact:
    name: Prof. Davis
    url: http://davisjam.github.io
    email: davisjam@purdue.edu
  license:
    name: Apache 2.0
    url: https://www.apache.org/licenses/LICENSE-2.0.html

paths:
  /health:
    get:
      summary: "Heartbeat check (BASELINE)"
      description: |
        Lightweight liveness probe. Returns HTTP 200 when the registry API is reachable.
      operationId: RegistryHealthHeartbeat
      responses:
        "200":
          description: Service reachable.
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    example: "ok"

  /health/components:
    get:
      summary: "Get component health details (NON-BASELINE)"
      description: |
        Return per-component health diagnostics, including status, active issues, and log references.
        Use this endpoint to power deeper observability dashboards or for incident debugging.
      operationId: RegistryHealthComponents
      parameters:
        - name: windowMinutes
          in: query
          description: "Length of the trailing observation window, in minutes (5-1440). Defaults to 60."
          required: false
          schema:
            type: integer
            minimum: 5
            maximum: 1440
            default: 60
        - name: includeTimeline
          in: query
          description: "Set to true to include per-component activity timelines sampled across the window."
          required: false
          schema:
            type: boolean
            default: false
      responses:
        "200":
          description: Component-level health detail.
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/HealthComponentCollection"

  /health/performance/workload:
    post:
      summary: "Trigger performance workload (NON-BASELINE)"
      description: |
        Trigger a performance workload test with specified number of concurrent clients.
        Returns immediately with a run_id for tracking. Workload executes asynchronously.
      operationId: TriggerPerformanceWorkload
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - num_clients
                - model_id
              properties:
                num_clients:
                  type: integer
                  description: Number of concurrent clients to simulate
                  example: 100
                model_id:
                  type: string
                  description: Model ID to test
                  example: "arnir0/Tiny-LLM"
                artifact_id:
                  type: string
                  description: Optional artifact ID
                duration_seconds:
                  type: integer
                  description: Duration of the workload in seconds
                  example: 300
      responses:
        "202":
          description: Workload accepted and started.
          content:
            application/json:
              schema:
                type: object
                properties:
                  run_id:
                    type: string
                    format: uuid
                  status:
                    type: string
                    example: "started"
                  estimated_completion:
                    type: string
                    format: date-time
        "400":
          description: Invalid request parameters.
        "500":
          description: Failed to start workload.

  /health/performance/results/{run_id}:
    get:
      summary: "Get performance workload results (NON-BASELINE)"
      description: |
        Retrieve aggregated performance metrics for a completed workload run.
      operationId: GetPerformanceResults
      parameters:
        - name: run_id
          in: path
          required: true
          description: Run ID returned from workload trigger
          schema:
            type: string
            format: uuid
      responses:
        "200":
          description: Performance results available.
          content:
            application/json:
              schema:
                type: object
                properties:
                  run_id:
                    type: string
                  metrics:
                    type: object
                    properties:
                      throughput_mbps:
                        type: number
                      mean_latency_ms:
                        type: number
                      p99_latency_ms:
                        type: number
                      success_rate:
                        type: number
        "404":
          description: Run ID not found.
        "500":
          description: Error retrieving results.

  /authenticate:
    put:
      summary: "Authenticate this user -- get an access token (NON-BASELINE)"
      description: |
        If your system supports the authentication scheme described in the spec, then:
        
        1. The obtained token should be provided to the other endpoints via the "X-Authorization" header.
        2. The "Authorization" header is *required* in your system.
        
        Otherwise, this endpoint should return HTTP 501 "Not implemented", and the "X-Authorization" header should be unused for the other endpoints.
      operationId: CreateAuthToken
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/AuthenticationRequest"
            examples:
              ExampleRequest:
                value:
                  user:
                    name: ece30861defaultadminuser
                    is_admin: true
                  secret:
                    password: correcthorsebatterystaple123(!__+@**(A'"`;DROP TABLE artifacts;
      responses:
        "200":
          description: Return an AuthenticationToken.
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/AuthenticationToken"
        "400":
          description: There is missing field(s) in the AuthenticationRequest or it is formed improperly.
        "401":
          description: The user or password is invalid.
        "501":
          description: This system does not support authentication.

  /auth/register:
    post:
      summary: "Register a new user (NON-BASELINE)"
      description: Register a new user account.
      operationId: RegisterUser
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - username
                - password
              properties:
                username:
                  type: string
                password:
                  type: string
      responses:
        "201":
          description: User registered successfully.
        "400":
          description: Invalid registration data.
        "409":
          description: User already exists.

  /auth/login:
    post:
      summary: "Login user (NON-BASELINE)"
      description: Authenticate user and receive access token.
      operationId: LoginUser
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - username
                - password
              properties:
                username:
                  type: string
                password:
                  type: string
      responses:
        "200":
          description: Login successful.
          content:
            application/json:
              schema:
                type: object
                properties:
                  access_token:
                    type: string
                  token_type:
                    type: string
                    example: "bearer"
        "401":
          description: Invalid credentials.

  /auth/me:
    get:
      summary: "Get current user info (NON-BASELINE)"
      description: Get information about the currently authenticated user.
      operationId: GetCurrentUser
      security:
        - BearerAuth: []
      responses:
        "200":
          description: User information.
          content:
            application/json:
              schema:
                type: object
                properties:
                  username:
                    type: string
                  is_admin:
                    type: boolean
        "401":
          description: Not authenticated.

  /auth/logout:
    post:
      summary: "Logout user (NON-BASELINE)"
      description: Invalidate the current user's access token.
      operationId: LogoutUser
      security:
        - BearerAuth: []
      responses:
        "200":
          description: Logout successful.
        "401":
          description: Not authenticated.

  /reset:
    delete:
      summary: "Reset the registry (BASELINE)"
      description: Reset the registry to a system default state.
      operationId: RegistryReset
      parameters:
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: false
      responses:
        "200":
          description: Registry is reset.
        "401":
          description: You do not have permission to reset the registry.
        "403":
          description: Authentication failed due to invalid or missing AuthenticationToken.

  /reset-rds:
    delete:
      summary: "Reset RDS database (NON-BASELINE)"
      description: Reset the RDS PostgreSQL database to a system default state.
      operationId: ResetRDS
      parameters:
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: false
      responses:
        "200":
          description: RDS database is reset.
        "401":
          description: You do not have permission to reset the database.
        "403":
          description: Authentication failed due to invalid or missing AuthenticationToken.

  /populate/s3/performance:
    post:
      summary: "Populate S3 performance path (NON-BASELINE)"
      description: Populate S3 with models for performance testing.
      operationId: PopulateS3Performance
      parameters:
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: false
      responses:
        "200":
          description: S3 performance path populated.
        "403":
          description: Authentication failed.

  /populate/rds/performance:
    post:
      summary: "Populate RDS performance path (NON-BASELINE)"
      description: Populate RDS with models for performance testing.
      operationId: PopulateRDSPerformance
      parameters:
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: false
      responses:
        "200":
          description: RDS performance path populated.
        "403":
          description: Authentication failed.

  /artifacts:
    post:
      summary: "Get the artifacts from the registry (BASELINE)"
      description: |
        Get any artifacts fitting the query.
        Search for artifacts satisfying the indicated query.
        
        If you want to enumerate all artifacts, provide an array with a single artifact_query whose name is "*".
        
        The response is paginated; the response header includes the offset to use in the next query.
      operationId: ArtifactsList
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: array
              items:
                $ref: "#/components/schemas/ArtifactQuery"
      parameters:
        - name: offset
          in: query
          description: "Provide this for pagination. If not provided, returns the first page of results."
          schema:
            $ref: "#/components/schemas/EnumerateOffset"
          required: false
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: true
      responses:
        "200":
          description: List of artifacts
          headers:
            offset:
              schema:
                $ref: "#/components/schemas/EnumerateOffset"
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: "#/components/schemas/ArtifactMetadata"
        "400":
          description: "There is missing field(s) in the artifact_query or it is formed improperly, or is invalid."
        "403":
          description: Authentication failed due to invalid or missing AuthenticationToken.
        "413":
          description: Too many artifacts returned.

  /artifacts/{artifact_type}/{id}:
    get:
      summary: "Interact with the artifact with this id (BASELINE)"
      description: Return this artifact.
      operationId: ArtifactRetrieve
      parameters:
        - name: artifact_type
          in: path
          required: true
          description: Type of artifact to fetch
          schema:
            $ref: "#/components/schemas/ArtifactType"
        - name: id
          in: path
          required: true
          description: id of artifact to fetch
          schema:
            $ref: "#/components/schemas/ArtifactID"
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: true
      responses:
        "200":
          description: Return the artifact. url is required.
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Artifact"
        "400":
          description: "There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid."
        "403":
          description: Authentication failed due to invalid or missing AuthenticationToken.
        "404":
          description: Artifact does not exist.

    put:
      summary: "Update this content of the artifact (BASELINE)"
      description: |
        The name and id must match.
        
        The artifact source (from artifact_data) will replace the previous contents.
      operationId: ArtifactUpdate
      parameters:
        - name: artifact_type
          in: path
          required: true
          description: Type of artifact to update
          schema:
            $ref: "#/components/schemas/ArtifactType"
        - name: id
          in: path
          required: true
          description: artifact id
          schema:
            $ref: "#/components/schemas/ArtifactID"
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: true
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Artifact"
      responses:
        "200":
          description: Artifact is updated.
        "400":
          description: "There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid."
        "403":
          description: Authentication failed due to invalid or missing AuthenticationToken.
        "404":
          description: Artifact does not exist.

    delete:
      summary: "Delete this artifact (NON-BASELINE)"
      description: Delete only the artifact that matches "id". (id is a unique identifier for an artifact)
      operationId: ArtifactDelete
      parameters:
        - name: artifact_type
          in: path
          required: true
          description: Type of artifact to delete
          schema:
            $ref: "#/components/schemas/ArtifactType"
        - name: id
          in: path
          required: true
          description: artifact id
          schema:
            $ref: "#/components/schemas/ArtifactID"
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: true
      responses:
        "200":
          description: Artifact is deleted.
        "400":
          description: "There is missing field(s) in the artifact_type or artifact_id or invalid"
        "403":
          description: Authentication failed due to invalid or missing AuthenticationToken.
        "404":
          description: Artifact does not exist.

  /artifact/{artifact_type}/{id}:
    get:
      summary: "Get artifact by type and id (BASELINE)"
      description: Return this artifact.
      operationId: ArtifactRetrieveByType
      parameters:
        - name: artifact_type
          in: path
          required: true
          description: Type of artifact to fetch
          schema:
            $ref: "#/components/schemas/ArtifactType"
        - name: id
          in: path
          required: true
          description: id of artifact to fetch
          schema:
            $ref: "#/components/schemas/ArtifactID"
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: true
      responses:
        "200":
          description: Return the artifact.
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Artifact"
        "400":
          description: "There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid."
        "403":
          description: Authentication failed due to invalid or missing AuthenticationToken.
        "404":
          description: Artifact does not exist.

  /artifact/{artifact_type}:
    post:
      summary: "Register a new artifact (BASELINE)"
      description: |
        Register a new artifact by providing a downloadable source url. Artifacts may share a name with existing entries; refer to the description above to see how an id is formed for an artifact.
      operationId: ArtifactCreate
      parameters:
        - name: artifact_type
          in: path
          required: true
          description: Type of artifact being ingested.
          schema:
            $ref: "#/components/schemas/ArtifactType"
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: true
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/ArtifactData"
      responses:
        "201":
          description: Success. Check the id in the returned metadata for the official ID.
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Artifact"
        "202":
          description: |
            Artifact ingest accepted but the rating pipeline deferred the evaluation. Use this when the package is stored but rating is performed asynchronously and the artifact is dropped silently if the rating later fails. Subsequent requests to `/rate` or any other endpoint with this artifact id should return 404 until a rating result exists.
        "400":
          description: There is missing field(s) in the artifact_data or it is formed improperly (must include a single url).
        "403":
          description: Authentication failed due to invalid or missing AuthenticationToken.
        "409":
          description: Artifact exists already.
        "424":
          description: Artifact is not registered due to the disqualified rating.

  /artifact/{artifact_type}/{id}/cost:
    get:
      summary: "Get the cost of an artifact (BASELINE)"
      description: Return the total cost of the artifact, and its dependencies
      operationId: ArtifactCost
      parameters:
        - name: artifact_type
          in: path
          required: true
          schema:
            $ref: "#/components/schemas/ArtifactType"
        - name: id
          in: path
          required: true
          schema:
            $ref: "#/components/schemas/ArtifactID"
        - name: dependency
          in: query
          schema:
            type: boolean
            default: false
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: true
      responses:
        "200":
          description: Return the total cost of the artifact, and its dependencies
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ArtifactCost"
        "400":
          description: "There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid."
        "403":
          description: Authentication failed due to invalid or missing AuthenticationToken.
        "404":
          description: Artifact does not exist.
        "500":
          description: The artifact cost calculator encountered an error.

  /artifact/{artifact_type}/{id}/audit:
    get:
      summary: "Retrieve audit entries for this artifact (NON-BASELINE)"
      description: Return the audit trail for this artifact.
      operationId: ArtifactAuditGet
      parameters:
        - name: artifact_type
          in: path
          required: true
          description: Type of artifact to audit
          schema:
            $ref: "#/components/schemas/ArtifactType"
        - name: id
          in: path
          required: true
          description: artifact id
          schema:
            $ref: "#/components/schemas/ArtifactID"
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: true
      responses:
        "200":
          description: Return the audit trail for this artifact.
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: "#/components/schemas/ArtifactAuditEntry"
        "400":
          description: "There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid."
        "403":
          description: Authentication failed due to invalid or missing AuthenticationToken.
        "404":
          description: Artifact does not exist.

  /artifact/byName/{name}:
    get:
      summary: "List artifact metadata for this name (NON-BASELINE)"
      description: Return metadata for each artifact matching this name.
      operationId: ArtifactByNameGet
      parameters:
        - name: name
          in: path
          required: true
          schema:
            $ref: "#/components/schemas/ArtifactName"
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: true
      responses:
        "200":
          description: Return artifact metadata entries that match the provided name.
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: "#/components/schemas/ArtifactMetadata"
        "400":
          description: "There is missing field(s) in the artifact_name or it is formed improperly, or is invalid."
        "403":
          description: Authentication failed due to invalid or missing AuthenticationToken.
        "404":
          description: No such artifact.

  /artifact/byRegEx:
    post:
      summary: "Get any artifacts fitting the regular expression (BASELINE)"
      description: |
        Search for an artifact using regular expression over artifact names
        and READMEs. This is similar to search by name.
      operationId: ArtifactByRegExGet
      parameters:
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: true
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/ArtifactRegEx"
      responses:
        "200":
          description: Return a list of artifacts.
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: "#/components/schemas/ArtifactMetadata"
        "400":
          description: There is missing field(s) in the artifact_regex or it is formed improperly, or is invalid
        "403":
          description: Authentication failed due to invalid or missing AuthenticationToken.
        "404":
          description: No artifact found under this regex.

  /artifact/ingest:
    post:
      summary: "Ingest artifact (NON-BASELINE)"
      description: Ingest an artifact from external source (e.g., HuggingFace).
      operationId: ArtifactIngest
      parameters:
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: false
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                name:
                  type: string
                version:
                  type: string
                type:
                  type: string
          multipart/form-data:
            schema:
              type: object
              properties:
                name:
                  type: string
                version:
                  type: string
                type:
                  type: string
      responses:
        "200":
          description: Artifact ingested successfully.
        "400":
          description: Invalid ingest data.
        "403":
          description: Authentication failed.

  /artifact/model/{id}/rate:
    get:
      summary: "Get ratings for this model artifact (BASELINE)"
      description: Return the rating. Only use this if each metric was computed successfully.
      operationId: ModelArtifactRate
      parameters:
        - name: id
          in: path
          required: true
          schema:
            $ref: "#/components/schemas/ArtifactID"
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: true
      responses:
        "200":
          description: Return the rating.
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ModelRating"
        "400":
          description: "There is missing field(s) in the artifact_id or it is formed improperly, or is invalid."
        "403":
          description: Authentication failed due to invalid or missing AuthenticationToken.
        "404":
          description: Artifact does not exist.
        "500":
          description: The artifact rating system encountered an error while computing at least one metric.

  /artifact/model/{id}/lineage:
    get:
      summary: "Retrieve the lineage graph for this artifact (BASELINE)"
      description: Lineage graph extracted from structured metadata.
      operationId: ArtifactLineageGet
      parameters:
        - name: id
          in: path
          required: true
          description: artifact id
          schema:
            $ref: "#/components/schemas/ArtifactID"
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: true
      responses:
        "200":
          description: Lineage graph extracted from structured metadata.
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ArtifactLineageGraph"
        "400":
          description: "The lineage graph cannot be computed because the artifact metadata is missing or malformed."
        "403":
          description: Authentication failed due to invalid or missing AuthenticationToken.
        "404":
          description: Artifact does not exist.

  /artifact/model/{id}/license-check:
    post:
      summary: "Assess license compatibility for fine-tune and inference usage (BASELINE)"
      description: License compatibility analysis produced successfully.
      operationId: ArtifactLicenseCheck
      parameters:
        - name: id
          in: path
          required: true
          description: artifact id
          schema:
            $ref: "#/components/schemas/ArtifactID"
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: true
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/SimpleLicenseCheckRequest"
      responses:
        "200":
          description: License compatibility analysis produced successfully.
          content:
            application/json:
              schema:
                type: boolean
        "400":
          description: "The license check request is malformed or references an unsupported usage context."
        "403":
          description: Authentication failed due to invalid or missing AuthenticationToken.
        "404":
          description: The artifact or GitHub project could not be found.
        "502":
          description: External license information could not be retrieved.

  /artifact/model/{id}/download:
    get:
      summary: "Download model from S3 (NON-BASELINE)"
      description: Download model file from S3 storage.
      operationId: DownloadModel
      parameters:
        - name: id
          in: path
          required: true
          schema:
            $ref: "#/components/schemas/ArtifactID"
        - name: version
          in: query
          schema:
            type: string
            default: "main"
        - name: component
          in: query
          schema:
            type: string
            enum: [full, weights, datasets]
            default: "full"
        - name: path_prefix
          in: query
          schema:
            type: string
            enum: [models, performance]
            default: "models"
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: false
      responses:
        "200":
          description: Model file download.
          content:
            application/zip:
              schema:
                type: string
                format: binary
        "404":
          description: Model not found.
        "403":
          description: Authentication failed.

  /artifact/model/{id}/download-rds:
    get:
      summary: "Download model from RDS (NON-BASELINE)"
      description: Download model file from RDS PostgreSQL storage.
      operationId: DownloadModelRDS
      parameters:
        - name: id
          in: path
          required: true
          schema:
            $ref: "#/components/schemas/ArtifactID"
        - name: version
          in: query
          schema:
            type: string
            default: "main"
        - name: component
          in: query
          schema:
            type: string
            enum: [full, weights, datasets]
            default: "full"
        - name: path_prefix
          in: query
          schema:
            type: string
            enum: [models, performance]
            default: "models"
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: true
      responses:
        "200":
          description: Model file download.
          content:
            application/zip:
              schema:
                type: string
                format: binary
        "404":
          description: Model not found.
        "403":
          description: Authentication failed.

  /artifact/model/{id}/ingest-rds:
    post:
      summary: "Upload model to RDS (NON-BASELINE)"
      description: Upload model file directly to RDS PostgreSQL.
      operationId: UploadModelRDS
      parameters:
        - name: id
          in: path
          required: true
          schema:
            $ref: "#/components/schemas/ArtifactID"
        - name: version
          in: query
          schema:
            type: string
            default: "main"
        - name: path_prefix
          in: query
          schema:
            type: string
            enum: [models, performance]
            default: "models"
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: true
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                file:
                  type: string
                  format: binary
      responses:
        "200":
          description: Upload successful.
        "400":
          description: Invalid file or request.
        "403":
          description: Authentication failed.

  /package/{id}:
    get:
      summary: "Get package by ID (NON-BASELINE)"
      description: Retrieve package information by ID.
      operationId: GetPackage
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: false
      responses:
        "200":
          description: Package information.
        "404":
          description: Package not found.

  /package/{id}/rate:
    get:
      summary: "Get package rating (NON-BASELINE)"
      description: Retrieve rating information for a package.
      operationId: GetPackageRate
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
        - name: X-Authorization
          in: header
          description: Authentication token
          schema:
            $ref: "#/components/schemas/AuthenticationToken"
          required: false
      responses:
        "200":
          description: Package rating.
        "404":
          description: Package not found.

  /tracks:
    get:
      summary: "Get the list of tracks a student has planned to implement in their code"
      description: Return the list of tracks the student plans to implement
      operationId: GetTracks
      responses:
        "200":
          description: Return the list of tracks the student plans to implement
          content:
            application/json:
              schema:
                type: object
                properties:
                  plannedTracks:
                    type: array
                    description: "List of tracks the student plans to implement"
                    items:
                      type: string
                      enum:
                        - "Performance track"
                        - "Access control track"
                        - "High assurance track"
                        - "Other Security track"
        "500":
          description: The system encountered an error while retrieving the student's track information.

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    Artifact:
      description: Artifact envelope containing metadata and ingest details.
      required:
        - metadata
        - data
      type: object
      properties:
        metadata:
          $ref: "#/components/schemas/ArtifactMetadata"
        data:
          $ref: "#/components/schemas/ArtifactData"

    ArtifactData:
      description: |
        Source location for ingesting an artifact.
        
        Provide a single downloadable url pointing to a bundle that contains the artifact assets.
      required:
        - url
      type: object
      properties:
        url:
          description: Artifact source url used during ingest.
          type: string
          format: uri
        download_url:
          description: Direct download link served by your server for retrieving the stored artifact bundle. Present only in responses.
          type: string
          format: uri
          readOnly: true

    ArtifactType:
      description: "Artifact category."
      type: string
      enum:
        - model
        - dataset
        - code

    ArtifactID:
      description: "Unique identifier for use with artifact endpoints."
      example: "48472749248"
      type: string
      pattern: '^[a-zA-Z0-9\-]+$'

    ArtifactName:
      description: |
        Name of an artifact.
        
        - Names should only use typical "keyboard" characters.
        - The name "*" is reserved. See the `/artifacts` API for its meaning.
      type: string

    ArtifactMetadata:
      description: |
        The `name` is provided when uploading an artifact.
        
        The `id` is used as an internal identifier for interacting with existing artifacts and distinguishes artifacts that share a name.
      required:
        - name
        - id
        - type
      type: object
      properties:
        name:
          $ref: "#/components/schemas/ArtifactName"
        id:
          $ref: "#/components/schemas/ArtifactID"
        type:
          $ref: "#/components/schemas/ArtifactType"

    ArtifactQuery:
      description: ""
      required:
        - name
      type: object
      properties:
        name:
          $ref: "#/components/schemas/ArtifactName"
          description: ""
        types:
          description: Optional list of artifact types to filter results.
          type: array
          items:
            $ref: "#/components/schemas/ArtifactType"

    ArtifactAuditEntry:
      description: One entry in an artifact's audit history.
      required:
        - user
        - date
        - artifact
        - action
      type: object
      properties:
        user:
          $ref: "#/components/schemas/User"
          description: ""
        date:
          format: date-time
          description: Date of activity using ISO-8601 Datetime standard in UTC format.
          type: string
          example: 2023-03-23T23:11:15Z
        artifact:
          $ref: "#/components/schemas/ArtifactMetadata"
          description: ""
        action:
          description: ""
          enum:
            - CREATE
            - UPDATE
            - DOWNLOAD
            - RATE
            - AUDIT
          type: string

    ArtifactCost:
      description: Artifact Cost aggregates the total download size (in MB) required for the artifact, optionally including dependencies.
      type: object
      additionalProperties:
        type: object
        properties:
          standalone_cost:
            type: number
            description: The standalone cost of this artifact excluding dependencies. Required when `dependency = true` in the request.
          total_cost:
            type: number
            description: |
              The total cost of the artifact. When `dependency` is not set, this should return the standalone cost,
              and when it is set, this field should return the sum of the costs of all the dependencies.
        required:
          - total_cost

    ArtifactRegEx:
      description: ""
      required:
        - regex
      type: object
      properties:
        regex:
          description: |
            A regular expression over artifact names and READMEs that is
            used for searching for an artifact
          type: string

    ArtifactLineageNode:
      description: A single node in an artifact lineage graph.
      required:
        - node
      type: object
      properties:
        artifact_id:
          description: Unique identifier for the node (artifact or external dependency).
          $ref: "#/components/schemas/ArtifactID"
        name:
          description: Human-readable label for the node.
          type: string
          example: audience-classifier
        source:
          description: Provenance for how the node was discovered.
          type: string
          example: config_json
        metadata:
          description: Optional metadata captured for lineage analysis.
          type: object

    ArtifactLineageEdge:
      description: Directed relationship between two lineage nodes.
      required:
        - from_node_artifact_id
        - to_node_artifact_id
        - relationship
      type: object
      properties:
        from_node_artifact_id:
          description: Identifier of the upstream node.
          $ref: "#/components/schemas/ArtifactID"
        to_node_artifact_id:
          description: Identifier of the downstream node.
          $ref: "#/components/schemas/ArtifactID"
        relationship:
          description: Qualitative description of the edge.
          type: string
          example: fine_tuning_dataset

    ArtifactLineageGraph:
      description: Complete lineage graph for an artifact.
      required:
        - nodes
        - edges
      type: object
      properties:
        nodes:
          description: Nodes participating in the lineage graph.
          type: array
          items:
            $ref: "#/components/schemas/ArtifactLineageNode"
        edges:
          description: Directed edges describing lineage relationships.
          type: array
          items:
            $ref: "#/components/schemas/ArtifactLineageEdge"

    SimpleLicenseCheckRequest:
      description: Request payload for artifact license compatibility analysis.
      required:
        - github_url
      type: object
      properties:
        github_url:
          description: GitHub repository url to evaluate.
          type: string
          format: uri
          example: https://github.com/google-research/bert

    User:
      description: ""
      required:
        - name
        - is_admin
      type: object
      properties:
        name:
          description: ""
          type: string
          example: Alfalfa
        is_admin:
          description: Is this user an admin?
          type: boolean

    UserAuthenticationInfo:
      description: Authentication info for a user
      required:
        - password
      type: object
      properties:
        password:
          description: |
            "Password for a user. Per the spec, this should be a \"strong\" password."
          type: string

    ModelRating:
      description: Model rating summary generated by the evaluation service.
      required:
        - name
        - category
        - net_score
        - net_score_latency
        - ramp_up_time
        - ramp_up_time_latency
        - bus_factor
        - bus_factor_latency
        - performance_claims
        - performance_claims_latency
        - license
        - license_latency
        - dataset_and_code_score
        - dataset_and_code_score_latency
        - dataset_quality
        - dataset_quality_latency
        - code_quality
        - code_quality_latency
        - reproducibility
        - reproducibility_latency
        - reviewedness
        - reviewedness_latency
        - tree_score
        - tree_score_latency
        - size_score
        - size_score_latency
      type: object
      properties:
        name:
          description: Human-friendly label for the evaluated model.
          type: string
        category:
          description: Model category assigned during evaluation.
          type: string
        net_score:
          format: double
          description: Overall score synthesizing all metrics.
          type: number
        net_score_latency:
          format: double
          description: Time (seconds) required to compute `net_score`.
          type: number
        ramp_up_time:
          format: double
          description: Ease-of-adoption rating for the model.
          type: number
        ramp_up_time_latency:
          format: double
          description: Time (seconds) required to compute `ramp_up_time`.
          type: number
        bus_factor:
          format: double
          description: Team redundancy score for the upstream project.
          type: number
        bus_factor_latency:
          format: double
          description: Time (seconds) required to compute `bus_factor`.
          type: number
        performance_claims:
          format: double
          description: Alignment between stated and observed performance.
          type: number
        performance_claims_latency:
          format: double
          description: Time (seconds) required to compute `performance_claims`.
          type: number
        license:
          format: double
          description: Licensing suitability score.
          type: number
        license_latency:
          format: double
          description: Time (seconds) required to compute `license`.
          type: number
        dataset_and_code_score:
          format: double
          description: Availability and quality of accompanying datasets and code.
          type: number
        dataset_and_code_score_latency:
          format: double
          description: Time (seconds) required to compute `dataset_and_code_score`.
          type: number
        dataset_quality:
          format: double
          description: Quality rating for associated datasets.
          type: number
        dataset_quality_latency:
          format: double
          description: Time (seconds) required to compute `dataset_quality`.
          type: number
        code_quality:
          format: double
          description: Quality rating for provided code artifacts.
          type: number
        code_quality_latency:
          format: double
          description: Time (seconds) required to compute `code_quality`.
          type: number
        reproducibility:
          format: double
          description: Likelihood that reported results can be reproduced.
          type: number
        reproducibility_latency:
          format: double
          description: Time (seconds) required to compute `reproducibility`.
          type: number
        reviewedness:
          format: double
          description: Measure of peer or community review coverage.
          type: number
        reviewedness_latency:
          format: double
          description: Time (seconds) required to compute `reviewedness`.
          type: number
        tree_score:
          format: double
          description: Supply-chain health score for model dependencies.
          type: number
        tree_score_latency:
          format: double
          description: Time (seconds) required to compute `tree_score`.
          type: number
        size_score:
          description: Size suitability scores for common deployment targets.
          type: object
          required:
            - raspberry_pi
            - jetson_nano
            - desktop_pc
            - aws_server
          properties:
            raspberry_pi:
              format: double
              description: Size score for Raspberry Pi class devices.
              type: number
            jetson_nano:
              format: double
              description: Size score for Jetson Nano deployments.
              type: number
            desktop_pc:
              format: double
              description: Size score for desktop deployments.
              type: number
            aws_server:
              format: double
              description: Size score for cloud server deployments.
              type: number
        size_score_latency:
          description: Time (seconds) required to compute `size_score`.
          format: double
          type: number

    AuthenticationToken:
      description: |
        "The spec permits you to use any token format you like. You could, for example, look into JSON Web Tokens (\"JWT\", pronounced \"jots\"): https://jwt.io."
      type: string

    AuthenticationRequest:
      description: ""
      required:
        - user
        - secret
      type: object
      properties:
        user:
          $ref: "#/components/schemas/User"
          description: ""
        secret:
          $ref: "#/components/schemas/UserAuthenticationInfo"
          description: ""

    EnumerateOffset:
      description: Offset in pagination.
      type: string
      example: "1"

    HealthStatus:
      description: Aggregate health classification for monitored systems.
      type: string
      enum:
        - ok
        - degraded
        - critical
        - unknown

    HealthComponentCollection:
      description: Detailed health diagnostics broken down per component.
      required:
        - components
        - generated_at
      type: object
      properties:
        components:
          type: array
          items:
            $ref: "#/components/schemas/HealthComponentDetail"
        generated_at:
          description: Timestamp when the component report was created (UTC).
          type: string
          format: date-time
        window_minutes:
          description: Observation window applied to the component metrics.
          type: integer
          minimum: 5

    HealthComponentDetail:
      description: Detailed status, metrics, and log references for a component.
      required:
        - id
        - status
        - observed_at
      type: object
      properties:
        id:
          description: Stable identifier for the component.
          type: string
        display_name:
          description: Human readable component name.
          type: string
        status:
          $ref: "#/components/schemas/HealthStatus"
        observed_at:
          description: Timestamp when data for this component was last collected (UTC).
          type: string
          format: date-time
        description:
          description: Overview of the component's responsibility.
          type: string
        metrics:
          type: object
          additionalProperties:
            oneOf:
              - type: integer
              - type: number
              - type: string
              - type: boolean
        issues:
          type: array
          items:
            type: object
            properties:
              code:
                type: string
              severity:
                type: string
                enum: [info, warning, error]
              summary:
                type: string
              details:
                type: string
        timeline:
          type: array
          items:
            type: object
            properties:
              bucket:
                type: string
                format: date-time
              value:
                type: number
              unit:
                type: string
        logs:
          type: array
          items:
            type: object
            properties:
              label:
                type: string
              url:
                type: string
                format: uri
              tail_available:
                type: boolean
              last_updated_at:
                type: string
                format: date-time
```

## Endpoint Summary

### Health & System Endpoints
- `GET /health` - Heartbeat check (BASELINE)
- `GET /health/components` - Component health details (NON-BASELINE)
- `POST /health/performance/workload` - Trigger performance workload (NON-BASELINE)
- `GET /health/performance/results/{run_id}` - Get performance results (NON-BASELINE)

### Authentication Endpoints
- `PUT /authenticate` - Get access token (NON-BASELINE)
- `POST /auth/register` - Register new user (NON-BASELINE)
- `POST /auth/login` - Login user (NON-BASELINE)
- `GET /auth/me` - Get current user info (NON-BASELINE)
- `POST /auth/logout` - Logout user (NON-BASELINE)

### Registry Management
- `DELETE /reset` - Reset registry (BASELINE)
- `DELETE /reset-rds` - Reset RDS database (NON-BASELINE)
- `POST /populate/s3/performance` - Populate S3 performance path (NON-BASELINE)
- `POST /populate/rds/performance` - Populate RDS performance path (NON-BASELINE)

### Artifact Endpoints
- `POST /artifacts` - List artifacts (BASELINE)
- `GET /artifacts/{artifact_type}/{id}` - Get artifact (BASELINE)
- `PUT /artifacts/{artifact_type}/{id}` - Update artifact (BASELINE)
- `DELETE /artifacts/{artifact_type}/{id}` - Delete artifact (NON-BASELINE)
- `GET /artifact/{artifact_type}/{id}` - Get artifact by type (BASELINE)
- `POST /artifact/{artifact_type}` - Create artifact (BASELINE)
- `GET /artifact/{artifact_type}/{id}/cost` - Get artifact cost (BASELINE)
- `GET /artifact/{artifact_type}/{id}/audit` - Get artifact audit trail (NON-BASELINE)
- `GET /artifact/byName/{name}` - Get artifacts by name (NON-BASELINE)
- `POST /artifact/byRegEx` - Search artifacts by regex (BASELINE)
- `POST /artifact/ingest` - Ingest artifact (NON-BASELINE)

### Model-Specific Endpoints
- `GET /artifact/model/{id}/rate` - Get model rating (BASELINE)
- `GET /artifact/model/{id}/lineage` - Get model lineage (BASELINE)
- `POST /artifact/model/{id}/license-check` - Check license compatibility (BASELINE)
- `GET /artifact/model/{id}/download` - Download model from S3 (NON-BASELINE)
- `GET /artifact/model/{id}/download-rds` - Download model from RDS (NON-BASELINE)
- `POST /artifact/model/{id}/ingest-rds` - Upload model to RDS (NON-BASELINE)

### Package Endpoints
- `GET /package/{id}` - Get package (NON-BASELINE)
- `GET /package/{id}/rate` - Get package rating (NON-BASELINE)

### Tracks
- `GET /tracks` - Get planned tracks

## Notes

- All endpoints support optional authentication via `X-Authorization` or `Authorization` header unless otherwise specified
- BASELINE endpoints are required for the baseline specification
- NON-BASELINE endpoints are additional features beyond the baseline
- Query parameters with default values can be omitted
- Path parameters are required (e.g., `{id}`, `{artifact_type}`, `{name}`)
- RDS endpoints require RDS credentials to be configured
- S3 endpoints use S3 storage backend
- The `path_prefix` parameter accepts `"models"` or `"performance"` (default: `"models"`)
- The `component` parameter accepts `"full"`, `"weights"`, or `"datasets"` (default: `"full"`)

