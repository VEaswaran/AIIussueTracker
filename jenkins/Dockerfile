# =============================================================================
# ⚠️  NOT IN USE — Docker stages are disabled in the Jenkinsfile.
#
# To re-enable Docker:
#   1. Uncomment Docker Build + Docker Push stages in Jenkinsfile
#   2. Uncomment DOCKER_IMAGE, IMAGE_TAG, DOCKER_CREDS in Jenkinsfile env block
#   3. Add Jenkins credential: id=docker-registry-creds (Username/Password)
#   4. Set DOCKER_REGISTRY environment variable in Jenkins global config
#   5. Uncomment docker-workflow and docker-plugin in jenkins/required-plugins.txt
# =============================================================================

# =============================================================================
# AI Issue Tracker MCP — Dockerfile
# Used by Jenkinsfile stage: Docker Build
#
# Build args:
#   JAR_FILE  — relative path to the fat JAR  (default: target/ai-issue-tracker-mcp-1.0.0.jar)
#   APP_PORT  — port the app listens on        (default: 8082)
# =============================================================================

# ---- Stage 1: unpack the Spring Boot layered JAR for efficient layer caching ----
FROM eclipse-temurin:17-jre-alpine AS builder

ARG JAR_FILE=target/ai-issue-tracker-mcp-1.0.0.jar
WORKDIR /app

COPY ${JAR_FILE} app.jar

# Extract Spring Boot layers
RUN java -Djarmode=layertools -jar app.jar extract


# ---- Stage 2: lean runtime image ----
FROM eclipse-temurin:17-jre-alpine

ARG APP_PORT=8082
ENV SERVER_PORT=${APP_PORT}

# Non-root user for security
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

WORKDIR /app

# Copy layers in order of least → most frequently changed
COPY --from=builder /app/dependencies/          ./
COPY --from=builder /app/spring-boot-loader/    ./
COPY --from=builder /app/snapshot-dependencies/ ./
COPY --from=builder /app/application/           ./

EXPOSE ${APP_PORT}

# Health check — calls Spring Boot actuator if available, falls back to TCP
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD wget -qO- http://localhost:${APP_PORT}/actuator/health 2>/dev/null || \
        wget -qO- http://localhost:${APP_PORT}/mcp/messages   2>/dev/null || exit 1

ENTRYPOINT ["java", \
    "-XX:+UseContainerSupport", \
    "-XX:MaxRAMPercentage=75.0", \
    "-Djava.security.egd=file:/dev/./urandom", \
    "org.springframework.boot.loader.launch.JarLauncher"]

