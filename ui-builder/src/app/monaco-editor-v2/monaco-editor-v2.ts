import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { EditorComponent } from 'ngx-monaco-editor-v2';

@Component({
  selector: 'monaco-editor-v2',
  standalone: true,
  imports: [CommonModule, FormsModule, EditorComponent],
  templateUrl: './monaco-editor-v2.html',
  styleUrl: './monaco-editor-v2.css'
})
export class MonacoEditorV2Component implements OnChanges {
  @Input() language: 'python' | 'java' = 'python';
  @Input() code = '';
  @Input() toolName = '';
  @Output() codeChange = new EventEmitter<string>();
  private editorInstance: unknown = null;

  protected fontSize = 13;
  protected fontFamily = '"Roboto Mono", "Fira Code", "Courier New", monospace';
  protected readonly fontSizes = [12, 13, 14, 16, 18, 20];
  protected readonly fontFamilies = [
    '"Roboto Mono", "Fira Code", "Courier New", monospace',
    '"Fira Code", "Roboto Mono", "Courier New", monospace',
    '"Source Code Pro", "Roboto Mono", "Courier New", monospace',
    '"Cascadia Code", "Fira Code", "Courier New", monospace'
  ];
  protected openTabs: Array<'tool' | 'callbacks'> = ['tool'];
  protected activeTab: 'tool' | 'callbacks' = 'tool';

  editorOptions: Record<string, unknown> = {
    theme: 'vs-dark',
    automaticLayout: true,
    readOnly: false,
    domReadOnly: false,
    minimap: { enabled: true },
    fontSize: this.fontSize,
    fontFamily: this.fontFamily,
    lineNumbers: 'on',
    lineNumbersMinChars: 4,
    scrollBeyondLastLine: false,
    smoothScrolling: true,
    cursorSmoothCaretAnimation: 'on',
    renderLineHighlight: 'all',
    scrollbar: {
      verticalScrollbarSize: 8,
      horizontalScrollbarSize: 8
    },
    padding: { top: 10, bottom: 10 }
  };
  options: Record<string, unknown> = {
    ...this.editorOptions,
    language: this.language
  };

  ngOnChanges(changes: SimpleChanges) {
    this.ensureTabState();
    if (changes['language']) {
      this.options = {
        ...this.editorOptions,
        language: this.language
      };
    }
  }

 

  handleEditorInit(editor: unknown) {
    this.editorInstance = editor;
    const typedEditor = editor as {
      focus?: () => void;
      layout?: () => void;
      updateOptions?: (options: Record<string, unknown>) => void;
      onDidChangeModelContent?: (cb: () => void) => void;
      getValue?: () => string;
    };
    if (typedEditor.updateOptions) {
      typedEditor.updateOptions({ readOnly: false, domReadOnly: false });
    }
    setTimeout(() => {
      typedEditor.layout?.();
      typedEditor.focus?.();
    }, 0);
  }

  focusEditor() {
    const typedEditor = this.editorInstance as { focus?: () => void } | null;
    typedEditor?.focus?.();
  }

  setFontSize(size: number) {
    this.fontSize = size;
    this.updateEditorOptions();
  }

  setFontFamily(family: string) {
    this.fontFamily = family;
    this.updateEditorOptions();
  }

  closeTab(tab: 'tool' | 'callbacks', event: Event) {
    event.stopPropagation();
    this.openTabs = this.openTabs.filter((item) => item !== tab);
    if (!this.openTabs.includes(this.activeTab)) {
      this.activeTab = this.openTabs[0] ?? 'tool';
    }
  }

  selectTab(tab: 'tool' | 'callbacks') {
    if (!this.openTabs.includes(tab)) {
      this.openTabs = [...this.openTabs, tab];
    }
    this.activeTab = tab;
  }

  get hasOpenTabs() {
    return this.openTabs.length > 0;
  }

  get toolTabLabel() {
    const baseName = this.toolBaseName;
    return this.language === 'java' ? `${baseName}.java` : `${baseName}.py`;
  }

  get callbacksTabLabel() {
    return this.language === 'java' ? 'callbacks.java' : 'callbacks.py';
  }

  private updateEditorOptions() {
    this.editorOptions = {
      ...this.editorOptions,
      fontSize: this.fontSize,
      fontFamily: this.fontFamily
    };
    this.options = {
      ...this.editorOptions,
      language: this.language
    };
    const typedEditor = this.editorInstance as { updateOptions?: (options: Record<string, unknown>) => void } | null;
    typedEditor?.updateOptions?.({
      fontSize: this.fontSize,
      fontFamily: this.fontFamily
    });
  }

  private ensureTabState() {
    if (this.openTabs.length === 0) {
      this.openTabs = ['tool'];
      this.activeTab = 'tool';
    }
  }

  private get toolBaseName() {
    const rawName = this.toolName?.trim();
    if (!rawName) {
      return 'tool_handler';
    }
    return rawName
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '');
  }
}
