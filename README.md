[English version](./README-en.md)
# Nexus Insight

### La clave para abordar el problema e implementar la solución.

**Nexus Insight** la solución de inteligencia artificial analítica que resuelve la brecha entre la ambigüedad del lenguaje natural y la rigidez de las bases de datos relacionales (Text-to-SQL). A diferencia de los modelos monolíticos tradicionales, utiliza el paradigma **MAC-SQL**, una arquitectura de agentes especializados que garantiza seguridad, reducción de costos y precisión técnica.

---

### **1. Arquitectura de Innovación: Paradigma MAC-SQL**
El sistema divide la carga cognitiva en cuatro agentes operativos para optimizar el rendimiento:
* **Planner:** Actúa como enrutador inteligente para evitar procesos innecesarios en consultas no relacionadas con SQL.
* **Librarian:** Filtra esquemas de tablas relevantes y utiliza una caché en Redis (TTL de 300s) para minimizar la latencia.
* **Critic & Executor:** Un filtro de seguridad "Zero-Trust" que bloquea comandos peligrosos (DDL/DML) y realiza corrección automática de errores sintácticos.
* **Evaluator:** Traduce datos tabulares rígidos en respuestas ejecutivas fluidas.

### **2. Resultados y Benchmarking (Evidencia Basada en Datos)**
La implementación ha demostrado mejoras significativas sobre los modelos estándar:
* **Eficiencia Temporal:** Reducción del **50.5%** en los tiempos de espera del usuario (P50) gracias al enrutamiento del *Planner*.
* **Optimización de Costos:** Reducción del **62.5%** en costos de tokens y cómputo mediante la sustitución de ventanas de contexto costosas por lecturas en memoria (Redis).

### **3. Seguridad y Gobernanza (Enterprise Ready)**
El proyecto se alinea con los principios de IA responsable de Microsoft:
* **Seguridad Nativa:** Integración con **Azure AI Content Safety** para prevenir inyecciones de prompts y **Entra ID** para la gestión de identidades.
* **Control Humano (HITL):** Arquitectura que requiere consentimiento humano registrado para el despacho de insights críticos.
* **Transparencia:** Monitoreo en tiempo real de las decisiones de los agentes vía *Azure Web PubSub*.

### **4. Ecosistema Tecnológico y Futuro**
* **Infraestructura:** Solución nativa de Azure (Container Apps, SQL, Key Vault) desplegada mediante Infraestructura como Código (Bicep) y CI/CD.
* **Próximos pasos:** Integración con **Microsoft Teams** para aprobaciones autónomas y uso de **Model Context Protocol (MCP)** para generar automáticamente reportes en Power BI y PDFs ejecutivos.
