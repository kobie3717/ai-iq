#!/usr/bin/env node
/**
 * AI-IQ Session Logger Hook (PostToolUse)
 * Logs ALL tool executions to /tmp/ai-iq-session-log.jsonl for analysis
 * Exit 0 always - never blocks execution
 */

import { appendFileSync } from 'fs';
import { createInterface } from 'readline';

const SESSION_LOG = '/tmp/ai-iq-session-log.jsonl';

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

    const timestamp = new Date().toISOString();
    let logEntry = {
      timestamp,
      tool: toolName,
    };

    // Extract relevant info per tool type
    if (toolName === 'Bash') {
      const cmd = (toolInput.command || '').trim();
      const exitMatch = toolOutput.match(/Exit code: (\d+)/);
      const exitCode = exitMatch ? parseInt(exitMatch[1]) : null;

      // Get first 100 chars of output (excluding exit code line)
      const outputLines = toolOutput.split('\n');
      const outputPreview = outputLines
        .filter(line => !line.startsWith('Exit code:'))
        .join(' ')
        .substring(0, 100);

      logEntry.input = cmd;
      logEntry.exit_code = exitCode;
      logEntry.output_preview = outputPreview || '';
    } else if (toolName === 'Read') {
      logEntry.file_path = toolInput.file_path || '';
      logEntry.action = 'read';
      logEntry.offset = toolInput.offset;
      logEntry.limit = toolInput.limit;
    } else if (toolName === 'Edit') {
      logEntry.file_path = toolInput.file_path || '';
      logEntry.action = 'edit';
      // Don't log full content, just indicate it was modified
      logEntry.output_preview = 'File modified';
    } else if (toolName === 'Write') {
      logEntry.file_path = toolInput.file_path || '';
      logEntry.action = 'write';
      logEntry.output_preview = 'File written';
    } else if (toolName === 'Glob') {
      logEntry.pattern = toolInput.pattern || '';
      logEntry.action = 'glob';
      const matchCount = (toolOutput.match(/\n/g) || []).length;
      logEntry.output_preview = `${matchCount} matches`;
    } else if (toolName === 'Grep') {
      logEntry.pattern = toolInput.pattern || '';
      logEntry.action = 'grep';
      const matchCount = (toolOutput.match(/\n/g) || []).length;
      logEntry.output_preview = `${matchCount} matches`;
    } else {
      // Generic handler for other tools
      logEntry.input = JSON.stringify(toolInput).substring(0, 100);
      logEntry.output_preview = toolOutput.substring(0, 100);
    }

    // Append to JSONL file
    appendFileSync(SESSION_LOG, JSON.stringify(logEntry) + '\n');

    process.exit(0);
  } catch (err) {
    // Silent fail - never block
    process.exit(0);
  }
});
