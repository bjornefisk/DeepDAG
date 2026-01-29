# Dockerfile for Go orchestrator service
FROM golang:1.24-alpine AS builder

WORKDIR /app

# Copy Go modules and API proto for module replacement
COPY HDRP/orchestrator/go.mod HDRP/orchestrator/go.sum ./orchestrator/
COPY HDRP/api/ ./api/

WORKDIR /app/orchestrator
RUN go mod download

# Copy source code
COPY HDRP/orchestrator/ .

# Build the orchestrator
RUN CGO_ENABLED=0 GOOS=linux go build -o server ./cmd/server

# Runtime stage
FROM alpine:latest

# Install wget for health checks
RUN apk --no-cache add wget ca-certificates

WORKDIR /app

# Copy binary from builder
COPY --from=builder /app/orchestrator/server /app/orchestrator/server

# Copy config files
COPY HDRP/config/ /app/config/

# Expose gRPC port
EXPOSE 50055

# Run the server
CMD ["/app/orchestrator/server", "-port", "50055", "-config", "/app/config/config.yaml"]
