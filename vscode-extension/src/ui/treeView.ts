import * as vscode from "vscode";
import { Convention, ViolationResponse } from "../types";

interface TreeNode {
  type: "category" | "violation" | "convention";
  label: string;
  severity?: string;
  uri?: vscode.Uri;
  line?: number;
  description?: string;
  children?: TreeNode[];
  iconId?: string;
}

export class ForgeLineTreeProvider
  implements vscode.TreeDataProvider<TreeNode>
{
  private _onDidChangeTreeData = new vscode.EventEmitter<
    TreeNode | undefined | void
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private _violations = new Map<string, ViolationResponse[]>();
  private _conventions: Convention[] = [];

  getTreeItem(element: TreeNode): vscode.TreeItem {
    const item = new vscode.TreeItem(
      element.label,
      element.children && element.children.length > 0
        ? vscode.TreeItemCollapsibleState.Expanded
        : vscode.TreeItemCollapsibleState.None,
    );

    if (element.description) {
      item.description = element.description;
    }

    if (element.iconId) {
      item.iconPath = new vscode.ThemeIcon(element.iconId);
    }

    // Click-to-navigate for leaf nodes
    if (element.uri && element.line !== undefined) {
      const pos = new vscode.Position(element.line, 0);
      item.command = {
        command: "vscode.open",
        title: "Go to violation",
        arguments: [
          element.uri,
          { selection: new vscode.Range(pos, pos) },
        ],
      };
    }

    return item;
  }

  getChildren(element?: TreeNode): TreeNode[] {
    if (element) {
      return element.children ?? [];
    }
    return this._buildRoot();
  }

  refresh(
    violations: Map<string, ViolationResponse[]>,
    conventions?: Convention[],
  ): void {
    this._violations = violations;
    if (conventions !== undefined) {
      this._conventions = conventions;
    }
    this._onDidChangeTreeData.fire();
  }

  clearAll(): void {
    this._violations.clear();
    this._conventions = [];
    this._onDidChangeTreeData.fire();
  }

  private _buildRoot(): TreeNode[] {
    const errors: TreeNode[] = [];
    const warnings: TreeNode[] = [];
    const infos: TreeNode[] = [];

    for (const [uriStr, violations] of this._violations) {
      const uri = vscode.Uri.parse(uriStr);
      for (const v of violations) {
        const node: TreeNode = {
          type: "violation",
          label: v.message,
          severity: v.severity,
          uri,
          line: v.line_start - 1,
          description: `${vscode.workspace.asRelativePath(uri)}:${v.line_start}`,
          iconId:
            v.severity === "error"
              ? "error"
              : v.severity === "warning"
                ? "warning"
                : "info",
        };

        if (v.severity === "error") {
          errors.push(node);
        } else if (v.severity === "warning") {
          warnings.push(node);
        } else {
          infos.push(node);
        }
      }
    }

    const conventionNodes: TreeNode[] = this._conventions.map((c) => ({
      type: "convention" as const,
      label: c.name,
      description: c.description,
      iconId: "book",
    }));

    const categories: TreeNode[] = [];

    if (errors.length > 0) {
      categories.push({
        type: "category",
        label: `Errors (${errors.length})`,
        iconId: "error",
        children: errors,
      });
    }
    if (warnings.length > 0) {
      categories.push({
        type: "category",
        label: `Warnings (${warnings.length})`,
        iconId: "warning",
        children: warnings,
      });
    }
    if (infos.length > 0) {
      categories.push({
        type: "category",
        label: `Info (${infos.length})`,
        iconId: "info",
        children: infos,
      });
    }
    if (conventionNodes.length > 0) {
      categories.push({
        type: "category",
        label: `Conventions (${conventionNodes.length})`,
        iconId: "book",
        children: conventionNodes,
      });
    }

    return categories;
  }
}
