import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MonacoEditorV2Component } from '../monaco-editor-v2/monaco-editor-v2';
import toolRegistryData from '../../../data/tool-registry.json';

type ToolArgument = {
  name: string;
  type: 'String' | 'Integer' | 'Float' | 'Boolean' | 'Object' | 'Array';
  required: boolean;
  properties?: ToolArgument[];
};

type ToolItem = {
  id: string;
  name: string;
  type: 'Python Function' | 'Python REST API';
  description: string;
  arguments: ToolArgument[];
  outputs: string[];
  version: string;
};

@Component({
  selector: 'app-tools-menu',
  standalone: true,
  imports: [CommonModule, FormsModule, MonacoEditorV2Component],
  templateUrl: './tools-menu.html',
  styleUrl: './tools-menu.css'
})
export class ToolsMenuComponent {
  protected step: 1 | 2 | 3 | 4 | 5 = 1;
  protected mode: 'lookup' | 'new' | null = null;
  protected language: 'python' | 'java' | null = null;
  protected registry: 'global' | 'lookup' | 'create' | null = null;
  protected readonly registryName = this.findGlobalRegistryName();
  protected tools: ToolItem[] = [
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
  ];
  protected selectedToolId: string | null = this.tools[0]?.id ?? null;
  protected registryTab: 'arguments' | 'code' = 'arguments';
  protected code = '';
  protected toolOnboardingTab: 'arguments' | 'code' = 'arguments';
  protected newToolName = '';
  protected newToolType: ToolItem['type'] = 'Python Function';
  protected newToolDescription = '';
  protected newToolCode = '';
  protected newToolArguments: ToolArgument[] = [];
  protected readonly argumentTypes = ['String', 'Integer', 'Float', 'Boolean', 'Object', 'Array'] as const;
  protected readonly pythonTemplate = `def handler(payload: dict) -> dict:
    """Tool/Callback implementation."""
    return {"status": "ok", "payload": payload}
`;
  protected readonly javaTemplate = `public class ToolHandler {
    public static String handle(String payload) {
        return payload;
    }
}
`;

  get selectedTool(): ToolItem | null {
    if (!this.selectedToolId) {
      return this.tools[0] ?? null;
    }
    return this.tools.find((tool) => tool.id === this.selectedToolId) ?? this.tools[0] ?? null;
  }

  get canProceed() {
    if (this.step === 1) {
      return !!this.mode;
    }
    if (this.step === 2) {
      return !!this.language;
    }
    if (this.step === 3) {
      return this.registry === 'global';
    }
    return false;
  }

  get languageLabel() {
    if (!this.language) {
      return '';
    }
    return this.language === 'java' ? 'Java' : 'Python';
  }

  selectMode(mode: 'lookup' | 'new') {
    this.mode = mode;
  }

  selectLanguage(language: 'python' | 'java') {
    this.language = language;
    this.code = language === 'python' ? this.pythonTemplate : this.javaTemplate;
  }

  selectRegistry(registry: 'global' | 'lookup' | 'create') {
    this.registry = registry;
  }

  selectTool(toolId: string) {
    this.selectedToolId = toolId;
  }

  setRegistryTab(tab: 'arguments' | 'code') {
    this.registryTab = tab;
  }

  updateCode(code: string) {
    this.code = code;
  }

  nextStep() {
    if (!this.canProceed) {
      return;
    }
    if (this.step < 5) {
      this.step = (this.step + 1) as 1 | 2 | 3 | 4 | 5;
    }
  }

  backStep() {
    if (this.step === 1) {
      return;
    }
    this.step = (this.step - 1) as 1 | 2 | 3 | 4 | 5;
  }

  openToolOnboarding() {
    this.step = 5;
    this.toolOnboardingTab = 'arguments';
    this.newToolName = '';
    this.newToolType = 'Python Function';
    this.newToolDescription = '';
    this.newToolCode = this.pythonTemplate;
    this.newToolArguments = [];
  }

  setToolOnboardingTab(tab: 'arguments' | 'code') {
    this.toolOnboardingTab = tab;
  }

  addNewToolArgument() {
    const nextIndex = this.newToolArguments.length + 1;
    this.newToolArguments = [
      ...this.newToolArguments,
      { name: `argument_${nextIndex}`, type: 'String', required: false }
    ];
  }

  updateNewToolArgumentAtPath(
    path: number[],
    field: 'name' | 'type' | 'required',
    value: string | boolean
  ) {
    this.newToolArguments = this.updateArgumentAtPath(this.newToolArguments, path, (argument) => {
      const nextValue =
        field === 'type' && typeof value === 'string'
          ? (value as ToolArgument['type'])
          : value;
      return {
        ...argument,
        [field]: nextValue
      };
    });
  }

  removeNewToolArgumentAtPath(path: number[]) {
    this.newToolArguments = this.removeArgumentAtPath(this.newToolArguments, path);
  }

  defineObjectSchemaAtPath(path: number[]) {
    this.newToolArguments = this.updateArgumentAtPath(this.newToolArguments, path, (argument) => ({
      ...argument,
      properties: argument.properties ?? []
    }));
  }

  addObjectPropertyAtPath(path: number[]) {
    this.newToolArguments = this.updateArgumentAtPath(this.newToolArguments, path, (argument) => {
      const nextIndex = (argument.properties?.length ?? 0) + 1;
      const nextProperties = argument.properties ?? [];
      return {
        ...argument,
        properties: [
          ...nextProperties,
          { name: `property_${nextIndex}`, type: 'String', required: false }
        ]
      };
    });
  }

  schemaPreview(properties: ToolArgument[] | undefined) {
    if (!properties || properties.length === 0) {
      return '{}';
    }
    const schema = this.buildSchemaObject(properties);
    return JSON.stringify(schema, null, 2);
  }

  extendPath(path: number[], index: number) {
    return [...path, index];
  }

  private findGlobalRegistryName() {
    const registries = toolRegistryData.toolRegistry ?? [];
    const globalRegistry = registries.find((registry: { global?: boolean }) => registry.global);
    return globalRegistry?.toolRegistryName ?? '';
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

  private buildSchemaObject(properties: ToolArgument[]) {
    return properties.reduce<Record<string, unknown>>((acc, property) => {
      acc[property.name] = this.schemaValue(property);
      return acc;
    }, {});
  }

  private schemaValue(property: ToolArgument): unknown {
    if (property.type === 'Object') {
      return this.buildSchemaObject(property.properties ?? []);
    }
    if (property.type === 'Array') {
      if (property.properties && property.properties.length > 0) {
        return [this.buildSchemaObject(property.properties)];
      }
      return ['<array>'];
    }
    return `<${property.type.toLowerCase()}>`;
  }
}
