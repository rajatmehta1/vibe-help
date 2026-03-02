import * as vscode from "vscode";
import { AutoFix, ViolationResponse } from "../types";

/**
 * Parallel store bridging DiagnosticProvider and QuickFixProvider.
 * VS Code Diagnostic has no extensible data field, so we maintain
 * auto-fix data keyed by uri:line:policyId.
 */
export class ViolationDataStore implements vscode.Disposable {
  private _autoFixes: Map<string, AutoFix> = new Map();

  private _key(
    uri: vscode.Uri,
    line: number,
    policyId: string,
  ): string {
    return `${uri.toString()}:${line}:${policyId}`;
  }

  store(uri: vscode.Uri, violation: ViolationResponse): void {
    if (violation.auto_fix) {
      this._autoFixes.set(
        this._key(uri, violation.line_start - 1, violation.policy_id),
        violation.auto_fix,
      );
    }
  }

  get(
    uri: vscode.Uri,
    line: number,
    policyId: string,
  ): AutoFix | undefined {
    return this._autoFixes.get(this._key(uri, line, policyId));
  }

  clearUri(uri: vscode.Uri): void {
    const prefix = uri.toString();
    for (const key of this._autoFixes.keys()) {
      if (key.startsWith(prefix)) {
        this._autoFixes.delete(key);
      }
    }
  }

  clearAll(): void {
    this._autoFixes.clear();
  }

  dispose(): void {
    this._autoFixes.clear();
  }
}

export class ForgeLineQuickFixProvider
  implements vscode.CodeActionProvider
{
  public static readonly providedCodeActionKinds = [
    vscode.CodeActionKind.QuickFix,
  ];

  constructor(private readonly _dataStore: ViolationDataStore) {}

  provideCodeActions(
    document: vscode.TextDocument,
    _range: vscode.Range | vscode.Selection,
    context: vscode.CodeActionContext,
    _token: vscode.CancellationToken,
  ): vscode.CodeAction[] {
    const actions: vscode.CodeAction[] = [];

    for (const diagnostic of context.diagnostics) {
      if (diagnostic.source !== "ForgeLine") {
        continue;
      }

      // Auto-fix actions
      actions.push(
        ...this._createAutoFixActions(document, diagnostic),
      );

      // Suppress rule action
      const suppress = this._createSuppressAction(
        document,
        diagnostic,
      );
      if (suppress) {
        actions.push(suppress);
      }
    }

    return actions;
  }

  private _createAutoFixActions(
    document: vscode.TextDocument,
    diagnostic: vscode.Diagnostic,
  ): vscode.CodeAction[] {
    const ruleId = String(diagnostic.code ?? "");
    const autoFix = this._dataStore.get(
      document.uri,
      diagnostic.range.start.line,
      ruleId,
    );
    if (!autoFix) {
      return [];
    }

    const actions: vscode.CodeAction[] = [];

    if (autoFix.type === "replace" && autoFix.replacement !== undefined) {
      const action = new vscode.CodeAction(
        "Fix: Replace with suggested code",
        vscode.CodeActionKind.QuickFix,
      );
      const edit = new vscode.WorkspaceEdit();
      edit.replace(document.uri, diagnostic.range, autoFix.replacement);
      action.edit = edit;
      action.diagnostics = [diagnostic];
      action.isPreferred = true;
      actions.push(action);
    }

    if (autoFix.type === "rename" && autoFix.new_name !== undefined) {
      const action = new vscode.CodeAction(
        `Fix: Rename to "${autoFix.new_name}"`,
        vscode.CodeActionKind.QuickFix,
      );
      const edit = new vscode.WorkspaceEdit();
      edit.replace(document.uri, diagnostic.range, autoFix.new_name);
      action.edit = edit;
      action.diagnostics = [diagnostic];
      action.isPreferred = true;
      actions.push(action);
    }

    if (autoFix.type === "insert" && autoFix.insert_text !== undefined) {
      const action = new vscode.CodeAction(
        "Fix: Insert suggested code",
        vscode.CodeActionKind.QuickFix,
      );
      const edit = new vscode.WorkspaceEdit();
      const pos =
        autoFix.insert_position === "after"
          ? diagnostic.range.end
          : diagnostic.range.start;
      edit.insert(document.uri, pos, autoFix.insert_text);
      action.edit = edit;
      action.diagnostics = [diagnostic];
      action.isPreferred = true;
      actions.push(action);
    }

    return actions;
  }

  private _createSuppressAction(
    document: vscode.TextDocument,
    diagnostic: vscode.Diagnostic,
  ): vscode.CodeAction | undefined {
    const ruleId = diagnostic.code;
    if (!ruleId) {
      return undefined;
    }

    const action = new vscode.CodeAction(
      `Suppress ForgeLine rule: ${ruleId}`,
      vscode.CodeActionKind.QuickFix,
    );

    const line = diagnostic.range.start.line;
    const lineText = document.lineAt(line);
    const indent = lineText.text.match(/^(\s*)/)?.[1] ?? "";
    const commentPrefix = this._getCommentPrefix(document.languageId);
    const suppressComment = `${indent}${commentPrefix} forgeline-disable-next-line: ${ruleId}\n`;

    const edit = new vscode.WorkspaceEdit();
    edit.insert(document.uri, new vscode.Position(line, 0), suppressComment);
    action.edit = edit;
    action.diagnostics = [diagnostic];
    action.isPreferred = false;
    return action;
  }

  private _getCommentPrefix(languageId: string): string {
    switch (languageId) {
      case "python":
      case "ruby":
      case "shellscript":
      case "yaml":
        return "#";
      case "html":
      case "xml":
        return "<!--";
      case "css":
      case "scss":
      case "less":
        return "/*";
      default:
        return "//";
    }
  }
}
