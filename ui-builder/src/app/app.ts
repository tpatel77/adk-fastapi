import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { FlowCanvasComponent } from './flow-canvas/flow-canvas';
import { ToolsMenuComponent } from './tools-menu/tools-menu';
import { ToolsPanelComponent } from './tools-panel/tools-panel';

type ToolArgument = {
  name: string;
  type: 'String' | 'Integer' | 'Float' | 'Boolean' | 'Object' | 'Array';
  required: boolean;
  properties?: ToolArgument[];
};

type ToolDefinition = {
  id: string;
  name: string;
  type: 'Python Function' | 'Python REST API';
  description: string;
  arguments: ToolArgument[];
  outputs: string[];
  version: string;
};

@Component({
  selector: 'app-root',
  imports: [CommonModule, FlowCanvasComponent, ToolsMenuComponent, ToolsPanelComponent],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  protected readonly activeSection = signal<
    'home' | 'prompts' | 'workflows' | 'rag' | 'builder' | 'toolsCallbacks'
  >('home');
  protected readonly workflows = signal<{ id: string; name: string; updated: string }[]>([]);
  protected readonly menuOpen = signal(false);
  protected readonly builderTab = signal<'workflow' | 'tools' | 'callbacks' | 'yaml' | 'settings'>('workflow');
  protected readonly tools = signal<ToolDefinition[]>([
    {
      id: 'echo_tool',
      name: 'Echo Tool',
      type: 'Python Function',
      description: 'Returns the input payload for quick testing.',
      arguments: [{ name: 'payload', type: 'Object', required: true }],
      outputs: ['payload'],
      version: 'v1.0'
    },
    {
      id: 'add_numbers',
      name: 'Add Numbers',
      type: 'Python Function',
      description: 'Adds two numbers and returns the sum.',
      arguments: [
        { name: 'a', type: 'Float', required: true },
        { name: 'b', type: 'Float', required: true }
      ],
      outputs: ['sum'],
      version: 'v2.1'
    },
    {
      id: 'multiply_numbers',
      name: 'Multiply Numbers',
      type: 'Python Function',
      description: 'Multiplies values for batch computations.',
      arguments: [
        { name: 'a', type: 'Float', required: true },
        { name: 'b', type: 'Float', required: true }
      ],
      outputs: ['product'],
      version: 'v1.4'
    }
  ]);
  protected readonly selectedToolId = signal<string | null>(null);
  protected readonly samplePython = `def handle_request(payload: dict) -> dict:
    \"\"\"Sample callback/tool implementation.\"\"\"
    user = payload.get(\"user\", \"anonymous\")
    return {
        \"status\": \"ok\",
        \"message\": f\"Hello, {user}\",
        \"payload\": payload
    }
`;
  protected readonly sampleYaml = `name: capital_city
type: llm
instruction: x42-e8afe1df-b769-462d-b152-ac9a1bc8591a
instruction_variables:
  a: "{a}"
  b: "{b}"
description: Identify the capital city of the country
tools:
  - echo_tool
  - add_numbers
  - multiply_numbers
context:
  callbacks:
    on_agent_start: ["log_agent_start"]
    on_tool_start: ["log_tool_start"]
    on_tool_finish: ["log_tool_finish"]
    on_model_finish: ["log_model_finish"]
    on_agent_finish: ["log_agent_finish"]
    on_model_start: ["log_model_start"]
output_key: capital_city
`;
  constructor() {
    const initialTool = this.tools()[0];
    if (initialTool) {
      this.selectedToolId.set(initialTool.id);
    }
  }

  selectSection(section: 'home' | 'prompts' | 'workflows' | 'rag' | 'toolsCallbacks') {
    this.activeSection.set(section);
    this.menuOpen.set(false);
  }

  startNewWorkflow() {
    this.activeSection.set('builder');
    this.builderTab.set('workflow');
    this.menuOpen.set(false);
  }

  openBuilder() {
    this.activeSection.set('builder');
    this.builderTab.set('workflow');
    this.menuOpen.set(false);
  }

  backToWorkflows() {
    this.activeSection.set('workflows');
  }

  toggleMenu() {
    this.menuOpen.set(!this.menuOpen());
  }

  toggleMenuAndHome() {
    this.menuOpen.set(!this.menuOpen());
  }

  selectBuilderTab(tab: 'workflow' | 'tools' | 'callbacks' | 'yaml' | 'settings') {
    this.builderTab.set(tab);
  }

  openToolsCallbacks() {
    this.activeSection.set('toolsCallbacks');
    this.menuOpen.set(false);
  }

  selectTool(toolId: string) {
    this.selectedToolId.set(toolId);
  }

  selectedTool() {
    const toolId = this.selectedToolId();
    const tools = this.tools();
    if (!toolId) {
      return tools[0] ?? null;
    }
    return tools.find((tool) => tool.id === toolId) ?? tools[0] ?? null;
  }

  createTool(payload: { name: string; type: 'Python Function' | 'Python REST API' }) {
    const toolId = payload.name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '');
    const newTool = {
      id: toolId || `tool_${this.tools().length + 1}`,
      name: payload.name,
      type: payload.type,
      description:
        payload.type === 'Python REST API'
          ? 'HTTP REST API Integration tool.'
          : 'Local Python function that runs within the workflow.',
      arguments: [],
      outputs: [],
      version: 'v1.0'
    };
    this.tools.set([...this.tools(), newTool]);
    this.selectedToolId.set(newTool.id);
  }

  addToolArgument(toolId: string) {
    const tools = this.tools();
    const updated: ToolDefinition[] = tools.map((tool) => {
      if (tool.id !== toolId) {
        return tool;
      }
      const nextIndex = tool.arguments.length + 1;
      return {
        ...tool,
        arguments: [
          ...tool.arguments,
          { name: `argument_${nextIndex}`, type: 'String', required: false }
        ]
      };
    });
    this.tools.set(updated);
  }

  removeTool(toolId: string) {
    const remaining = this.tools().filter((tool) => tool.id !== toolId);
    this.tools.set(remaining);
    if (this.selectedToolId() === toolId) {
      this.selectedToolId.set(remaining[0]?.id ?? null);
    }
  }

  updateToolArgument(
    toolId: string,
    path: number[],
    field: 'name' | 'type' | 'required',
    value: string | boolean
  ) {
    this.updateToolArguments(toolId, (argumentsList) =>
      this.updateArgumentAtPath(argumentsList, path, (argument) => {
        const nextValue =
          field === 'type' && typeof value === 'string'
            ? (value as ToolArgument['type'])
            : value;
        return {
          ...argument,
          [field]: nextValue
        };
      })
    );
  }

  defineObjectSchema(toolId: string, path: number[]) {
    this.updateToolArguments(toolId, (argumentsList) =>
      this.updateArgumentAtPath(argumentsList, path, (argument) => ({
        ...argument,
        properties: argument.properties ?? []
      }))
    );
  }

  addObjectProperty(toolId: string, path: number[]) {
    this.updateToolArguments(toolId, (argumentsList) =>
      this.updateArgumentAtPath(argumentsList, path, (argument) => {
        const nextIndex = (argument.properties?.length ?? 0) + 1;
        const nextProperties = argument.properties ?? [];
        return {
          ...argument,
          properties: [
            ...nextProperties,
            { name: `property_${nextIndex}`, type: 'String', required: false }
          ]
        };
      })
    );
  }

  removeToolArgument(toolId: string, path: number[]) {
    this.updateToolArguments(toolId, (argumentsList) => this.removeArgumentAtPath(argumentsList, path));
  }

  private updateToolArguments(
    toolId: string,
    updater: (argumentsList: ToolArgument[]) => ToolArgument[]
  ) {
    const updated: ToolDefinition[] = this.tools().map((tool) => {
      if (tool.id !== toolId) {
        return tool;
      }
      return {
        ...tool,
        arguments: updater(tool.arguments)
      };
    });
    this.tools.set(updated);
  }

  private updateArgumentAtPath(
    argumentsList: ToolArgument[],
    path: number[],
    updater: (argument: ToolArgument) => ToolArgument
  ): ToolArgument[] {
    if (path.length === 0) {
      return argumentsList;
    }
    const [index, ...rest] = path;
    return argumentsList.map((argument, argIndex) => {
      if (argIndex !== index) {
        return argument;
      }
      if (rest.length === 0) {
        return updater(argument);
      }
      const nextProperties = argument.properties ?? [];
      return {
        ...argument,
        properties: this.updateArgumentAtPath(nextProperties, rest, updater)
      };
    });
  }

  private removeArgumentAtPath(argumentsList: ToolArgument[], path: number[]): ToolArgument[] {
    if (path.length === 0) {
      return argumentsList;
    }
    if (path.length === 1) {
      const indexToRemove = path[0];
      return argumentsList.filter((_, idx) => idx !== indexToRemove);
    }
    const [index, ...rest] = path;
    return argumentsList.map((argument, argIndex) => {
      if (argIndex !== index) {
        return argument;
      }
      const nextProperties = argument.properties ?? [];
      return {
        ...argument,
        properties: this.removeArgumentAtPath(nextProperties, rest)
      };
    });
  }
}
