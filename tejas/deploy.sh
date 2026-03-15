#!/usr/bin/env bash
# ==========================================================================
# Tejas -- Deployment Script
#
# Builds and deploys the Tejas application to Google Cloud Run.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Docker installed (for local builds)
#   - GCP project created with billing enabled
#
# Usage:
#   ./deploy.sh                    # Deploy with defaults
#   ./deploy.sh --project my-proj  # Specify project
#   ./deploy.sh --region us-east1  # Specify region
#   ./deploy.sh --local            # Build locally instead of Cloud Build
# ==========================================================================

set -euo pipefail

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="tejas-backend"
FRONTEND_SERVICE_NAME="tejas-frontend"
REPO_NAME="tejas"
IMAGE_NAME="backend"
FRONTEND_IMAGE_NAME="frontend"
USE_CLOUD_BUILD=true

# --------------------------------------------------------------------------
# Parse Arguments
# --------------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case $1 in
        --project)
            PROJECT_ID="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --local)
            USE_CLOUD_BUILD=false
            shift
            ;;
        --help)
            echo "Usage: ./deploy.sh [--project PROJECT_ID] [--region REGION] [--local]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

if [[ -z "$PROJECT_ID" ]]; then
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null || true)
    if [[ -z "$PROJECT_ID" ]]; then
        echo "ERROR: No project ID specified."
        echo "Set GCP_PROJECT_ID or use --project flag or run: gcloud config set project YOUR_PROJECT"
        exit 1
    fi
fi

echo "======================================"
echo "  Tejas Deployment"
echo "======================================"
echo "  Project:  $PROJECT_ID"
echo "  Region:   $REGION"
echo "  Service:  $SERVICE_NAME"
echo "======================================"
echo ""

# --------------------------------------------------------------------------
# Step 1: Enable Required APIs
# --------------------------------------------------------------------------

echo "[1/6] Enabling required GCP APIs..."
gcloud services enable \
    run.googleapis.com \
    firestore.googleapis.com \
    storage.googleapis.com \
    secretmanager.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    aiplatform.googleapis.com \
    --project="$PROJECT_ID" \
    --quiet

echo "  APIs enabled."

# --------------------------------------------------------------------------
# Step 2: Create Artifact Registry Repository (if not exists)
# --------------------------------------------------------------------------

echo "[2/6] Setting up Artifact Registry..."
if ! gcloud artifacts repositories describe "$REPO_NAME" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    &>/dev/null; then

    gcloud artifacts repositories create "$REPO_NAME" \
        --repository-format=docker \
        --location="$REGION" \
        --project="$PROJECT_ID" \
        --description="Tejas container images" \
        --quiet

    echo "  Repository created."
else
    echo "  Repository already exists."
fi

# --------------------------------------------------------------------------
# Step 3: Build Container Image
# --------------------------------------------------------------------------

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:latest"

echo "[3/6] Building container image..."

if $USE_CLOUD_BUILD; then
    echo "  Using Cloud Build..."
    gcloud builds submit backend/ \
        --tag="$IMAGE_URI" \
        --project="$PROJECT_ID" \
        --quiet
else
    echo "  Building locally..."
    gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
    docker build -t "$IMAGE_URI" backend/
    docker push "$IMAGE_URI"
fi

echo "  Image built: $IMAGE_URI"

# --------------------------------------------------------------------------
# Step 4: Create Firestore Database (if not exists)
# --------------------------------------------------------------------------

echo "[4/6] Setting up Firestore..."
if ! gcloud firestore databases describe \
    --project="$PROJECT_ID" \
    &>/dev/null; then

    gcloud firestore databases create \
        --project="$PROJECT_ID" \
        --location=nam5 \
        --quiet

    echo "  Firestore database created."
else
    echo "  Firestore database already exists."
fi

# --------------------------------------------------------------------------
# Step 5: Deploy to Cloud Run
# --------------------------------------------------------------------------

echo "[5/6] Deploying to Cloud Run..."
GCS_BUCKET_NAME="${PROJECT_ID}-tejas-captures"
gcloud run deploy "$SERVICE_NAME" \
    --image="$IMAGE_URI" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --platform=managed \
    --allow-unauthenticated \
    --port=8080 \
    --cpu=2 \
    --memory=1Gi \
    --timeout=3600 \
    --session-affinity \
    --min-instances=0 \
    --max-instances=10 \
    --set-env-vars="ENVIRONMENT=production,GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION},USE_VERTEX_AI=true,GCS_BUCKET_NAME=${GCS_BUCKET_NAME}" \
    --quiet

echo "  Deployed."

# --------------------------------------------------------------------------
# Step 6: Get Service URL
# --------------------------------------------------------------------------

echo "[6/6] Retrieving service URL..."
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --format="value(status.url)")

echo ""
echo "======================================"
echo "  Deployment Complete"
echo "======================================"
echo "  Service URL: $SERVICE_URL"
echo "  Health:      ${SERVICE_URL}/health"
echo "  WebSocket:   ${SERVICE_URL/https/wss}/ws/stream"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Set the Gemini API key secret:"
echo "     echo -n 'YOUR_KEY' | gcloud secrets versions add tejas-gemini-api-key \\"
echo "       --data-file=- --project=${PROJECT_ID}"
echo ""
echo "  2. Seed reference data (hazmat ERG + medical protocols):"
echo "     curl -X POST ${SERVICE_URL}/api/seed"
echo ""
echo "  3. Deploy the frontend and set CORS:"
echo "     FRONTEND_IMAGE=\"${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${FRONTEND_IMAGE_NAME}:latest\""
echo "     gcloud builds submit frontend/ --tag=\"\$FRONTEND_IMAGE\" --project=${PROJECT_ID}"
echo "     gcloud run deploy ${FRONTEND_SERVICE_NAME} \\"
echo "       --image=\"\$FRONTEND_IMAGE\" \\"
echo "       --region=${REGION} --project=${PROJECT_ID} \\"
echo "       --allow-unauthenticated --port=80 \\"
echo "       --set-env-vars=\"BACKEND_URL=${SERVICE_URL}\" \\"
echo "       --build-arg VITE_WS_URL=${SERVICE_URL/https/wss}/ws/stream"
echo ""
echo "  4. After the frontend deploys, get its URL:"
echo "     FRONTEND_URL=\$(gcloud run services describe ${FRONTEND_SERVICE_NAME} \\"
echo "       --region=${REGION} --project=${PROJECT_ID} --format='value(status.url)')"
echo "     echo \"Frontend: \$FRONTEND_URL\""
echo ""
echo "  5. Update backend CORS to allow the frontend origin:"
echo "     gcloud run services update ${SERVICE_NAME} \\"
echo "       --region=${REGION} --project=${PROJECT_ID} \\"
echo "       --update-env-vars=\"ALLOWED_ORIGINS=[\\\"\$FRONTEND_URL\\\",\\\"http://localhost:5173\\\"]\""
echo "======================================"
