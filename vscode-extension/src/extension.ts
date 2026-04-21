import * as vscode from 'vscode';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

function getProjectName(): string {
    const config = vscode.workspace.getConfiguration('agentmemory');
    const configured = config.get<string>('project');
    if (configured && configured.trim()) {
        return configured;
    }
    const workspace = vscode.workspace.workspaceFolders?.[0];
    if (workspace) {
        return workspace.name;
    }
    return 'default';
}

async function runAgentMemory(args: string[]): Promise<string> {
    const project = getProjectName();
    const cmd = `agentmemory ${args.join(' ')} --project "${project}"`;
    try {
        const { stdout } = await execAsync(cmd);
        return stdout;
    } catch (err: any) {
        // Fallback to python module path
        const fallback = `python -m agentmemory.cli ${args.join(' ')} --project "${project}"`;
        const { stdout } = await execAsync(fallback);
        return stdout;
    }
}

export function activate(context: vscode.ExtensionContext) {
    // Capture memory
    const capture = vscode.commands.registerCommand('agentmemory.capture', async () => {
        const editor = vscode.window.activeTextEditor;
        let defaultText = '';
        if (editor && !editor.selection.isEmpty) {
            defaultText = editor.document.getText(editor.selection);
        }

        const content = await vscode.window.showInputBox({
            prompt: 'Memory content',
            value: defaultText,
            placeHolder: 'What did you learn or decide?'
        });
        if (!content) { return; }

        const category = await vscode.window.showQuickPick(
            ['fact', 'decision', 'action', 'preference', 'error'],
            { placeHolder: 'Memory category' }
        );
        if (!category) { return; }

        try {
            const result = await runAgentMemory(['capture', content, '--category', category]);
            vscode.window.showInformationMessage(`Memory captured: ${result.trim()}`);
        } catch (err: any) {
            vscode.window.showErrorMessage(`Capture failed: ${err.message}`);
        }
    });

    // Recall memories
    const recall = vscode.commands.registerCommand('agentmemory.recall', async () => {
        try {
            const result = await runAgentMemory(['recall']);
            const panel = vscode.window.createWebviewPanel(
                'agentmemoryRecall',
                'AgentMemory — Recall',
                vscode.ViewColumn.One,
                {}
            );
            panel.webview.html = `<html><body><pre>${result}</pre></body></html>`;
        } catch (err: any) {
            vscode.window.showErrorMessage(`Recall failed: ${err.message}`);
        }
    });

    // Search memories
    const search = vscode.commands.registerCommand('agentmemory.search', async () => {
        const keyword = await vscode.window.showInputBox({
            prompt: 'Search memories',
            placeHolder: 'Keyword...'
        });
        if (!keyword) { return; }

        try {
            const result = await runAgentMemory(['search', keyword]);
            vscode.window.showInformationMessage(result.trim());
        } catch (err: any) {
            vscode.window.showErrorMessage(`Search failed: ${err.message}`);
        }
    });

    // Load context brief
    const load = vscode.commands.registerCommand('agentmemory.load', async () => {
        try {
            const result = await runAgentMemory(['load']);
            await vscode.env.clipboard.writeText(result);
            vscode.window.showInformationMessage('Context brief copied to clipboard! Paste into your agent.');
        } catch (err: any) {
            vscode.window.showErrorMessage(`Load failed: ${err.message}`);
        }
    });

    // Sync CLAUDE.md
    const sync = vscode.commands.registerCommand('agentmemory.sync', async () => {
        try {
            const result = await runAgentMemory(['sync']);
            vscode.window.showInformationMessage(`Synced: ${result.trim()}`);
        } catch (err: any) {
            vscode.window.showErrorMessage(`Sync failed: ${err.message}`);
        }
    });

    // Auto-capture on save (if enabled)
    const saveListener = vscode.workspace.onDidSaveTextDocument(async (doc) => {
        const config = vscode.workspace.getConfiguration('agentmemory');
        if (!config.get<boolean>('autoCapture')) { return; }

        const relative = vscode.workspace.asRelativePath(doc.uri);
        if (relative.includes('node_modules') || relative.includes('__pycache__')) {
            return;
        }

        try {
            await runAgentMemory(['capture', `Edited ${relative}`, '--category', 'action', '--tags', 'vscode,auto']);
        } catch {
            // Silent fail for auto-capture
        }
    });

    context.subscriptions.push(capture, recall, search, load, sync, saveListener);
}

export function deactivate() {}
