#!/usr/bin/env node
/**
 * AI-IQ Tool Capture Hook (PostToolUse)
 * Captures significant tool executions as workflow memories
 * Exit 0 always - never blocks execution
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { createInterface } from 'readline';
import { execSync } from 'child_process';

const RATE_LIMIT_FILE = '/tmp/ai-iq-tool-capture-last.txt';
const RATE_LIMIT_SECONDS = 10;

// Commands to skip (too noisy, not meaningful)
const SKIP_COMMANDS = new Set([
  'ls', 'cd', 'pwd', 'cat', 'head', 'tail', 'echo',
  'git status', 'git log', 'git diff', 'git show',
  'npm list', 'which', 'whoami', 'date', 'df', 'free',
  'ps', 'top', 'history', 'env', 'printenv',
  'grep', 'find', 'locate', 'wc', 'sort', 'uniq',
  'less', 'more', 'vi', 'vim', 'nano', 'man',
  'memory-tool', 'mem'  // Avoid recursive capture
]);

// Significant keywords that make a command worth capturing
const SIGNIFICANT_KEYWORDS = new Set([
  'docker', 'git push', 'git commit', 'npm publish', 'npm install',
  'deploy', 'restart', 'systemctl', 'service', 'pm2',
  'python', 'node', 'cargo', 'make', 'build',
  'test', 'pytest', 'jest', 'npm test'
]);

// Read JSON from stdin
const rl = createInterface({ input: process.stdin });
let inputData = '';

rl.on('line', (line) => {
  inputData += line;
});

rl.on('close', () => {
  try {
    const data = JSON.parse(inputData);
    const toolName = data.tool_name || '';
    const toolOutput = String(data.tool_result || '');
    const toolInput = data.tool_input || {};

    // Rate limiting: max 1 capture per 10 seconds
    if (existsSync(RATE_LIMIT_FILE)) {
      const lastCapture = parseInt(readFileSync(RATE_LIMIT_FILE, 'utf8') || '0');
      const now = Math.floor(Date.now() / 1000);
      if (now - lastCapture < RATE_LIMIT_SECONDS) {
        process.exit(0); // Skip if within rate limit window
      }
    }

    let shouldCapture = false;
    let category = 'workflow';
    let content = '';

    // 1. Capture ERRORS from Bash
    if (toolName === 'Bash') {
      const isError = toolOutput.includes('Exit code') && !toolOutput.includes('Exit code: 0');

      if (isError) {
        category = 'error';
        const cmd = toolInput.command || '';
        const errorMsg = toolOutput.split('\n').slice(0, 3).join(' ').substring(0, 200);
        content = `Bash error: ${cmd} | ${errorMsg}`;
        shouldCapture = true;
      } else {
        // 2. Capture SUCCESSFUL significant Bash commands
        const cmd = (toolInput.command || '').trim();

        // Skip if empty or in skip list
        if (!cmd) {
          process.exit(0);
        }

        // Check if command starts with any skip pattern
        const cmdStart = cmd.split(/[\s;&|]/)[0]; // First token
        if (SKIP_COMMANDS.has(cmdStart)) {
          process.exit(0);
        }

        // Skip very short commands (likely noise)
        if (cmd.length < 10) {
          process.exit(0);
        }

        // Only capture if command contains significant keywords
        const cmdLower = cmd.toLowerCase();
        const hasSignificantKeyword = Array.from(SIGNIFICANT_KEYWORDS).some(kw =>
          cmdLower.includes(kw)
        );

        if (hasSignificantKeyword) {
          content = `Ran: ${cmd} (exit code: 0)`;
          shouldCapture = true;
        }
      }
    } else if (toolName === 'Edit') {
      // 3. Capture file edits (just file path)
      const filePath = toolInput.file_path || '';
      if (filePath && !filePath.includes('/tmp/')) {
        content = `Edited ${filePath}`;
        shouldCapture = true;
      }
    } else if (toolName === 'Write') {
      // 4. Capture file writes (just file path)
      const filePath = toolInput.file_path || '';
      if (filePath && !filePath.includes('/tmp/')) {
        content = `Created ${filePath}`;
        shouldCapture = true;
      }
    } else if (toolName === 'Agent') {
      // 5. Capture agent spawns
      const description = toolInput.description || '';
      if (description) {
        content = `Spawned agent: ${description.substring(0, 100)}`;
        shouldCapture = true;
      }
    }

    // Capture if criteria met
    if (shouldCapture && content) {
      // Update rate limit
      const now = Math.floor(Date.now() / 1000);
      writeFileSync(RATE_LIMIT_FILE, String(now));

      // Call memory-tool to add memory
      try {
        execSync(`memory-tool add ${category} "${content.replace(/"/g, '\\"')}" --tags hook,auto-capture,tool-use --source hook`, {
          stdio: 'ignore',
          timeout: 2000
        });
      } catch (err) {
        // Silent fail - memory-tool might have deduped or failed
      }
    }

    process.exit(0);
  } catch (err) {
    // Silent fail - never block
    process.exit(0);
  }
});
