export interface LlmConfig {
  nodeId: string;
  name: string;
  instruction: string;
  description: string;
  outputKey: string;
  instructionVariables: Array<{ key: string; value: string }>;
  tools: string[];
  callbacks: string[];
}
