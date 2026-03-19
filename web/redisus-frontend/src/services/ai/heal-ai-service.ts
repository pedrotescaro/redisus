export type NeuralAnalysisResult = {
  woundType: string;
  confidence: number;
  tissueComposition: {
    granulation: number;
    slough: number;
    necrosis: number;
  };
  riskLevel: "low" | "moderate" | "high";
  recommendations: string[];
};

const baseUrl = process.env.NEXT_PUBLIC_HEAL_AI_API_URL;

export async function analyzeWoundImage(imageFile: File): Promise<NeuralAnalysisResult> {
  const formData = new FormData();
  formData.append("image", imageFile);

  // Placeholder da chamada para a API externa Python.
  // Ajuste endpoint, payload e autenticacao quando o backend estiver publicado.
  const response = await fetch(`${baseUrl}/analyze`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Falha ao analisar imagem na API de IA.");
  }

  return response.json() as Promise<NeuralAnalysisResult>;
}
