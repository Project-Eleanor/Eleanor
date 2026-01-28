import {
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnDestroy,
  OnInit,
  Output,
  ViewChild,
  AfterViewInit,
  forwardRef,
  NgZone
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import type * as Monaco from 'monaco-editor';

// Monaco types - will be loaded dynamically
declare const monaco: typeof Monaco;

export interface MonacoEditorOptions {
  theme?: string;
  language?: string;
  minimap?: { enabled: boolean };
  lineNumbers?: 'on' | 'off' | 'relative';
  fontSize?: number;
  wordWrap?: 'on' | 'off' | 'wordWrapColumn' | 'bounded';
  scrollBeyondLastLine?: boolean;
  automaticLayout?: boolean;
  readOnly?: boolean;
  tabSize?: number;
  renderWhitespace?: 'none' | 'boundary' | 'selection' | 'trailing' | 'all';
}

@Component({
  selector: 'app-monaco-editor',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="monaco-editor-container" #editorContainer></div>
  `,
  styles: [`
    :host {
      display: block;
      width: 100%;
      height: 100%;
    }

    .monaco-editor-container {
      width: 100%;
      height: 100%;
      min-height: 150px;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      overflow: hidden;
    }

    :host(.focused) .monaco-editor-container {
      border-color: var(--accent);
    }
  `],
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => MonacoEditorComponent),
      multi: true
    }
  ]
})
export class MonacoEditorComponent implements OnInit, AfterViewInit, OnDestroy, ControlValueAccessor {
  @ViewChild('editorContainer', { static: true }) editorContainer!: ElementRef;

  @Input() options: MonacoEditorOptions = {};
  @Input() language = 'kql';

  @Output() editorReady = new EventEmitter<Monaco.editor.IStandaloneCodeEditor>();
  @Output() executeQuery = new EventEmitter<string>();

  private editor: Monaco.editor.IStandaloneCodeEditor | null = null;
  private value = '';
  private monacoLoaded = false;

  private onChange: (value: string) => void = () => {};
  private onTouched: () => void = () => {};

  constructor(private ngZone: NgZone, private elementRef: ElementRef) {}

  ngOnInit(): void {
    this.loadMonaco();
  }

  ngAfterViewInit(): void {
    if (this.monacoLoaded) {
      this.initEditor();
    }
  }

  ngOnDestroy(): void {
    if (this.editor) {
      this.editor.dispose();
    }
  }

  writeValue(value: string): void {
    this.value = value || '';
    if (this.editor) {
      this.editor.setValue(this.value);
    }
  }

  registerOnChange(fn: (value: string) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    if (this.editor) {
      this.editor.updateOptions({ readOnly: isDisabled });
    }
  }

  private loadMonaco(): void {
    // Check if Monaco is already loaded
    if (typeof monaco !== 'undefined') {
      this.monacoLoaded = true;
      this.registerLanguages();
      this.initEditor();
      return;
    }

    // Load Monaco from CDN
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/loader.js';
    script.onload = () => {
      (window as any).require.config({
        paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' }
      });

      (window as any).require(['vs/editor/editor.main'], () => {
        this.monacoLoaded = true;
        this.registerLanguages();
        this.ngZone.run(() => this.initEditor());
      });
    };
    document.head.appendChild(script);
  }

  private registerLanguages(): void {
    // Register KQL language
    monaco.languages.register({ id: 'kql' });

    monaco.languages.setMonarchTokensProvider('kql', {
      keywords: [
        'where', 'project', 'extend', 'summarize', 'sort', 'take', 'top',
        'limit', 'order', 'by', 'asc', 'desc', 'join', 'union', 'distinct',
        'count', 'sum', 'avg', 'min', 'max', 'dcount', 'ago', 'now', 'bin',
        'contains', 'startswith', 'endswith', 'has', 'in', 'between', 'matches',
        'and', 'or', 'not', 'true', 'false', 'null'
      ],
      operators: ['==', '!=', '<', '>', '<=', '>=', '=~', '!~', '|', '!'],

      tokenizer: {
        root: [
          [/[a-zA-Z_]\w*/, {
            cases: {
              '@keywords': 'keyword',
              '@default': 'identifier'
            }
          }],
          [/"([^"\\]|\\.)*$/, 'string.invalid'],
          [/"/, 'string', '@string_double'],
          [/'/, 'string', '@string_single'],
          [/\d+/, 'number'],
          [/[{}()\[\]]/, '@brackets'],
          [/[;,.]/, 'delimiter'],
          [/\/\/.*$/, 'comment'],
          [/[|]/, 'operator.pipe'],
          [/[=><!]=?|&&|\|\|/, 'operator'],
        ],
        string_double: [
          [/[^\\"]+/, 'string'],
          [/\\./, 'string.escape'],
          [/"/, 'string', '@pop']
        ],
        string_single: [
          [/[^\\']+/, 'string'],
          [/\\./, 'string.escape'],
          [/'/, 'string', '@pop']
        ]
      }
    });

    // KQL language configuration
    monaco.languages.setLanguageConfiguration('kql', {
      comments: { lineComment: '//' },
      brackets: [
        ['{', '}'],
        ['[', ']'],
        ['(', ')']
      ],
      autoClosingPairs: [
        { open: '{', close: '}' },
        { open: '[', close: ']' },
        { open: '(', close: ')' },
        { open: '"', close: '"' },
        { open: "'", close: "'" }
      ]
    });

    // Register ES|QL language (similar to KQL but with FROM syntax)
    monaco.languages.register({ id: 'esql' });

    monaco.languages.setMonarchTokensProvider('esql', {
      keywords: [
        'FROM', 'from', 'WHERE', 'where', 'EVAL', 'eval', 'STATS', 'stats',
        'SORT', 'sort', 'LIMIT', 'limit', 'KEEP', 'keep', 'DROP', 'drop',
        'RENAME', 'rename', 'DISSECT', 'dissect', 'GROK', 'grok', 'ENRICH', 'enrich',
        'AND', 'and', 'OR', 'or', 'NOT', 'not', 'LIKE', 'like', 'RLIKE', 'rlike',
        'IN', 'in', 'IS', 'is', 'NULL', 'null', 'TRUE', 'true', 'FALSE', 'false',
        'BY', 'by', 'ASC', 'asc', 'DESC', 'desc', 'NULLS', 'nulls', 'FIRST', 'first', 'LAST', 'last',
        'AS', 'as', 'COUNT', 'count', 'SUM', 'sum', 'AVG', 'avg', 'MIN', 'min', 'MAX', 'max'
      ],
      operators: ['==', '!=', '<', '>', '<=', '>=', '=', '|', '!'],

      tokenizer: {
        root: [
          [/[a-zA-Z_]\w*/, {
            cases: {
              '@keywords': 'keyword',
              '@default': 'identifier'
            }
          }],
          [/"([^"\\]|\\.)*$/, 'string.invalid'],
          [/"/, 'string', '@string'],
          [/\d+(\.\d+)?/, 'number'],
          [/[{}()\[\]]/, '@brackets'],
          [/[;,.]/, 'delimiter'],
          [/\/\/.*$/, 'comment'],
          [/[|]/, 'operator.pipe'],
          [/[=><!]=?|&&|\|\|/, 'operator'],
        ],
        string: [
          [/[^\\"]+/, 'string'],
          [/\\./, 'string.escape'],
          [/"/, 'string', '@pop']
        ]
      }
    });

    monaco.languages.setLanguageConfiguration('esql', {
      comments: { lineComment: '//' },
      brackets: [
        ['{', '}'],
        ['[', ']'],
        ['(', ')']
      ],
      autoClosingPairs: [
        { open: '{', close: '}' },
        { open: '[', close: ']' },
        { open: '(', close: ')' },
        { open: '"', close: '"' }
      ]
    });

    // Register KQL completion provider
    monaco.languages.registerCompletionItemProvider('kql', {
      provideCompletionItems: (model: any, position: any) => {
        const suggestions = [
          // Keywords
          ...['where', 'project', 'extend', 'summarize', 'sort', 'take', 'join', 'union']
            .map(kw => ({
              label: kw,
              kind: monaco.languages.CompletionItemKind.Keyword,
              insertText: kw,
              detail: 'KQL keyword'
            })),
          // Operators
          ...['contains', 'startswith', 'endswith', 'has', 'in', 'between', 'and', 'or', 'not']
            .map(op => ({
              label: op,
              kind: monaco.languages.CompletionItemKind.Operator,
              insertText: op,
              detail: 'KQL operator'
            })),
          // Functions
          ...['count()', 'sum()', 'avg()', 'min()', 'max()', 'dcount()', 'ago()', 'now()', 'bin()']
            .map(fn => ({
              label: fn.replace('()', ''),
              kind: monaco.languages.CompletionItemKind.Function,
              insertText: fn,
              detail: 'KQL function'
            })),
          // Common fields
          ...['@timestamp', 'event.category', 'event.action', 'host.name', 'user.name', 'process.name', 'source.ip', 'destination.ip']
            .map(field => ({
              label: field,
              kind: monaco.languages.CompletionItemKind.Field,
              insertText: field,
              detail: 'Common field'
            }))
        ];

        return { suggestions };
      }
    });

    // Register ES|QL completion provider
    monaco.languages.registerCompletionItemProvider('esql', {
      provideCompletionItems: (model: any, position: any) => {
        const suggestions = [
          // Keywords
          ...['FROM', 'WHERE', 'EVAL', 'STATS', 'SORT', 'LIMIT', 'KEEP', 'DROP', 'RENAME', 'BY']
            .map(kw => ({
              label: kw,
              kind: monaco.languages.CompletionItemKind.Keyword,
              insertText: kw,
              detail: 'ES|QL keyword'
            })),
          // Operators
          ...['AND', 'OR', 'NOT', 'LIKE', 'RLIKE', 'IN', 'IS NULL', 'IS NOT NULL']
            .map(op => ({
              label: op,
              kind: monaco.languages.CompletionItemKind.Operator,
              insertText: op,
              detail: 'ES|QL operator'
            })),
          // Functions
          ...['COUNT(*)', 'SUM()', 'AVG()', 'MIN()', 'MAX()', 'TO_STRING()', 'TO_INT()', 'DATE_FORMAT()']
            .map(fn => ({
              label: fn.replace('()', '').replace('(*)', ''),
              kind: monaco.languages.CompletionItemKind.Function,
              insertText: fn,
              detail: 'ES|QL function'
            })),
          // Common indices
          ...['logs-*', 'metrics-*', 'security-*', 'filebeat-*', 'winlogbeat-*']
            .map(idx => ({
              label: idx,
              kind: monaco.languages.CompletionItemKind.Value,
              insertText: idx,
              detail: 'Common index pattern'
            }))
        ];

        return { suggestions };
      }
    });

    // Define Eleanor dark theme for Monaco
    monaco.editor.defineTheme('eleanor-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [
        { token: 'keyword', foreground: '58a6ff', fontStyle: 'bold' },
        { token: 'operator', foreground: 'c9d1d9' },
        { token: 'operator.pipe', foreground: 'ff7b72', fontStyle: 'bold' },
        { token: 'string', foreground: 'a5d6ff' },
        { token: 'string.escape', foreground: '79c0ff' },
        { token: 'number', foreground: '79c0ff' },
        { token: 'comment', foreground: '8b949e', fontStyle: 'italic' },
        { token: 'identifier', foreground: 'c9d1d9' },
        { token: 'delimiter', foreground: '8b949e' }
      ],
      colors: {
        'editor.background': '#0d1117',
        'editor.foreground': '#c9d1d9',
        'editor.lineHighlightBackground': '#161b22',
        'editor.selectionBackground': '#264f78',
        'editorCursor.foreground': '#58a6ff',
        'editorLineNumber.foreground': '#8b949e',
        'editorLineNumber.activeForeground': '#c9d1d9',
        'editor.selectionHighlightBackground': '#3392ff22',
        'editorBracketMatch.background': '#3392ff44',
        'editorBracketMatch.border': '#3392ff'
      }
    });
  }

  private initEditor(): void {
    if (!this.editorContainer?.nativeElement || this.editor) {
      return;
    }

    const defaultOptions: MonacoEditorOptions = {
      theme: 'eleanor-dark',
      language: this.language,
      minimap: { enabled: false },
      lineNumbers: 'on',
      fontSize: 14,
      wordWrap: 'on',
      scrollBeyondLastLine: false,
      automaticLayout: true,
      tabSize: 2,
      renderWhitespace: 'none'
    };

    const editorOptions = { ...defaultOptions, ...this.options, value: this.value };

    this.editor = monaco.editor.create(this.editorContainer.nativeElement, editorOptions);

    // Listen for content changes
    this.editor.onDidChangeModelContent(() => {
      const value = this.editor.getValue();
      this.ngZone.run(() => {
        this.value = value;
        this.onChange(value);
      });
    });

    // Listen for focus/blur
    this.editor.onDidFocusEditorText(() => {
      this.elementRef.nativeElement.classList.add('focused');
      this.ngZone.run(() => this.onTouched());
    });

    this.editor.onDidBlurEditorText(() => {
      this.elementRef.nativeElement.classList.remove('focused');
    });

    // Add Ctrl+Enter keybinding to execute query
    this.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
      this.ngZone.run(() => {
        this.executeQuery.emit(this.editor.getValue());
      });
    });

    this.editorReady.emit(this.editor);
  }

  /**
   * Focus the editor
   */
  focus(): void {
    if (this.editor) {
      this.editor.focus();
    }
  }

  /**
   * Get current value
   */
  getValue(): string {
    return this.editor ? this.editor.getValue() : this.value;
  }

  /**
   * Set value
   */
  setValue(value: string): void {
    this.value = value;
    if (this.editor) {
      this.editor.setValue(value);
    }
  }

  /**
   * Insert text at cursor position
   */
  insertText(text: string): void {
    if (this.editor) {
      const selection = this.editor.getSelection();
      const range = new monaco.Range(
        selection.startLineNumber,
        selection.startColumn,
        selection.endLineNumber,
        selection.endColumn
      );
      this.editor.executeEdits('', [{ range, text }]);
    }
  }
}
