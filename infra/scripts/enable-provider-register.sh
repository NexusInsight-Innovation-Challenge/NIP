#!/bin/bash
set -euo pipefail

# ==================================
# REGISTRATION OF SUPPLIERS REQUIRED 
# REGISTRO DE PROVEDORES NECESARIOS
# ==================================

# Identidad administrada | Managed Identity
az provider register --namespace Microsoft.ManagedIdentity

# Observavilidad y monitoreo | Observability and monitoring
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.Insights
az provider register --namespace Microsoft.KeyVault

# Almacenamiento y datos | Storage and data
az provider register --namespace Microsoft.Storage
az provider register --namespace Microsoft.Sql
az provider register --namespace Microsoft.ContainerRegistry

# Azure AI y servicios relacionados | Azure AI and related services
az provider register --namespace Microsoft.CognitiveServices
az provider register --namespace Microsoft.MachineLearningServices

# Mensajería y comunicación | Messaging and communication
az provider register --namespace Microsoft.WebPubSub
az provider register --namespace Microsoft.SignalRService
az provider register --namespace Microsoft.EventGrid

# Cómputo y redes | Compute and networking
az provider register --namespace Microsoft.Web
az provider register --namespace Microsoft.Network

# Gateway / API Management
az provider register --namespace Microsoft.ApiManagement

# Autorización y RBAC | Authorization and RBAC
az provider register --namespace Microsoft.Authorization

sleep 3

az provider list --query "[?registrationState!='Registered']"

echo "✅ The required suppliers registration has been completed succesfully."