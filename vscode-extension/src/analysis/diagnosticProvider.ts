import * as vscode from "vscode";
import { SeverityLevel, ViolationResponse } from "../types";

export class DiagnosticProvider implements vscode.Disposable {
  private readonly _collection: vscode.DiagnosticCollection;

  constructor() {
    this._collection =
      vscode.languages.createDiagnosticCollection("ForgeLine");
  }

  showViolations(
    uri: vscode.Uri,
    violations: ViolationResponse[],
  ): void {
    const diagnostics = violations.map((v) => this._toDiagnostic(v));
    this._collection.set(uri, diagnostics);
  }

  addViolations(
    uri: vscode.Uri,
    violations: ViolationResponse[],
  ): void {
    const existing = this._collection.get(uri) ?? [];
    const newDiagnostics = violations.map((v) => this._toDiagnostic(v));
    this._collection.set(uri, [...existing, ...newDiagnostics]);
  }

  clearDiagnostics(uri: vscode.Uri): void {
    this._collection.delete(uri);
  }

  clearAll(): void {
    this._collection.clear();
  }

  getDiagnosticCount(): number {
    let count = 0;
    this._collection.forEach((_uri, diagnostics) => {
      count += diagnostics.length;
    });
    return count;
  }

  private _toDiagnostic(
    violation: ViolationResponse,
  ): vscode.Diagnostic {
    // Backend uses 1-based lines/columns; VS Code uses 0-based
    const range = new vscode.Range(
      new vscode.Position(
        Math.max(0, violation.line_start - 1),
        Math.max(0, violation.column_start - 1),
      ),
      new vscode.Position(
        Math.max(0, violation.line_end - 1),
        Math.max(0, violation.column_end - 1),
      ),
    );

    const severity = this._mapSeverity(violation.severity);
    const message = violation.suggestion
      ? `${violation.message}\nSuggestion: ${violation.suggestion}`
      : violation.message;

    const diagnostic = new vscode.Diagnostic(range, message, severity);
    diagnostic.source = "ForgeLine";
    diagnostic.code = violation.policy_id;

    return diagnostic;
  }

  private _mapSeverity(
    severity: SeverityLevel,
  ): vscode.DiagnosticSeverity {
    switch (severity) {
      case "error":
        return vscode.DiagnosticSeverity.Error;
      case "warning":
        return vscode.DiagnosticSeverity.Warning;
      case "info":
        return vscode.DiagnosticSeverity.Information;
      default:
        return vscode.DiagnosticSeverity.Warning;
    }
  }

  dispose(): void {
    this._collection.dispose();
  }
}
