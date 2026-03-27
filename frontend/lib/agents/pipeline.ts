import {
  AgentContext,
  AgentInput,
  AgentIntent,
  AgentResult,
} from "@/lib/agents/contracts";

const intentDictionary: Array<{ intent: AgentIntent; words: string[] }> = [
  {
    intent: "architecture",
    words: ["arquitectura", "estructura", "patrón", "solid"],
  },
  {
    intent: "performance",
    words: ["performance", "rendimiento", "optimizar", "latencia"],
  },
  {
    intent: "security",
    words: ["seguridad", "auth", "autenticación", "xss", "csrf"],
  },
  { intent: "frontend", words: ["frontend", "ui", "ux", "tailwind", "react"] },
  { intent: "backend", words: ["backend", "api", "route", "server", "db"] },
];

const classifyIntent = (input: AgentInput): AgentIntent => {
  const normalized = input.text.toLowerCase();

  const match = intentDictionary.find(({ words }) =>
    words.some((word) => normalized.includes(word)),
  );

  return match?.intent ?? "general";
};

const buildContext = (input: AgentInput, intent: AgentIntent): AgentContext => {
  const focusAreas = [
    "Code quality",
    "Bugs y edge cases",
    "Performance",
    "Security",
  ];

  if (intent === "frontend") {
    focusAreas.unshift("Diseño visual consistente");
  }

  if (intent === "backend") {
    focusAreas.unshift("Estabilidad del contrato API");
  }

  if (intent === "security") {
    focusAreas.unshift("Validación de entrada y exposición mínima");
  }

  const riskLevel: AgentContext["riskLevel"] =
    input.text.length > 600 ? "high" : "medium";

  return {
    intent,
    focusAreas,
    riskLevel,
  };
};

const createResponse = (
  input: AgentInput,
  context: AgentContext,
): AgentResult => {
  const preface = `Analicé tu solicitud con foco ${context.intent} y prioricé compatibilidad completa en Next + Azure Web PubSub.`;

  const recommendations = [
    "Separar responsabilidades en módulos de dominio, transporte y UI para mantener SOLID.",
    "Aplicar validación estricta en cada endpoint y nunca exponer secretos al cliente.",
    "Emitir eventos de estado y streaming para evitar bloqueos perceptibles en la UI.",
    "Eliminar mocks y código muerto para reducir deuda técnica y riesgo de regresiones.",
    "Mantener contratos tipados para eventos realtime y payloads API.",
  ];

  const content =
    `${preface}\n\n` +
    `Resumen de tu prompt: "${input.text.slice(0, 220)}${input.text.length > 220 ? "..." : ""}"\n\n` +
    `Mejoras sugeridas:\n${recommendations.map((item, index) => `${index + 1}. ${item}`).join("\n")}`;

  const checkpoints = [
    "Intención detectada",
    "Contexto enriquecido",
    "Respuesta generada",
  ];

  return { content, checkpoints };
};

export const runAgentPipeline = (input: AgentInput): AgentResult => {
  const intent = classifyIntent(input);
  const context = buildContext(input, intent);

  return createResponse(input, context);
};
