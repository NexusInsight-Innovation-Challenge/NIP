#!/bin/bash

set -e

# Variables
ACR_NAME="nipACRzngovxusmkn3y"
RESOURCE_GROUP="nip-rg"
WEB_APP_NAME="nip-app-chat-zngovxusmkn3y"

# Obtén el hash del commit
TIMESTAMP_HASH=$(git rev-parse --short HEAD)

echo "======================================"
echo "🚀 Despliegue de innovation-chat"
echo "======================================"
echo "Tag: $TIMESTAMP_HASH"
echo ""

# Build local
echo "🏗️  [1/3] Construyendo imagen..."
docker build --target runner \
  -t $ACR_NAME.azurecr.io/innovation-chat:$TIMESTAMP_HASH \
  -t $ACR_NAME.azurecr.io/innovation-chat:latest \
  .

# Login con token
echo "🔐 [2/3] Conectando a ACR..."
TOKEN=$(az acr login --name $ACR_NAME --expose-token --output tsv --query accessToken)
echo $TOKEN | docker login $ACR_NAME.azurecr.io --username 00000000-0000-0000-0000-000000000000 --password-stdin

# Push a ACR
echo "📤 [2/3] Subiendo imágenes a ACR..."
docker push $ACR_NAME.azurecr.io/innovation-chat:$TIMESTAMP_HASH
docker push $ACR_NAME.azurecr.io/innovation-chat:latest

# Reiniciar Web App para aplicar cambios
echo "🔄 Reiniciando Web App..."
az webapp restart \
  --name $WEB_APP_NAME \
  --resource-group $RESOURCE_GROUP

echo ""
echo "======================================"
echo "✅ Despliegue completado exitosamente"
echo "======================================"
echo "Imagen desplegada:"
echo "  $ACR_NAME.azurecr.io/innovation-chat:$TIMESTAMP_HASH"
echo ""