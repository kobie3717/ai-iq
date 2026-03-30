#!/usr/bin/env node
/**
 * Search Feedback Hook (PostToolUse)
 *
 * Automatically logs feedback when Claude Code:
 * 1. Runs `memory-tool search` (captures search_id)
 * 2. Subsequently runs `memory-tool get <id>` (marks that memory as used)
 *
 * This creates the feedback loop automatically without manual input.
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';
import { execSync } from 'child_process';

// Session state file (tracks current search context)
const SESSION_FILE = '/tmp/claude-search-context.json';

function loadSession() {
  if (!existsSync(SESSION_FILE)) {
    return { search_id: null, used_ids: [] };
  }
  try {
    return JSON.parse(readFileSync(SESSION_FILE, 'utf8'));
  } catch {
    return { search_id: null, used_ids: [] };
  }
}

function saveSession(data) {
  try {
    writeFileSync(SESSION_FILE, JSON.stringify(data, null, 2));
  } catch (err) {
    // Silent fail
  }
}

function logFeedback(search_id, used_ids) {
  if (!search_id || used_ids.length === 0) return;

  try {
    const cmd = `memory-tool feedback ${search_id} ${used_ids.join(',')}`;
    execSync(cmd, { stdio: 'ignore' });
  } catch (err) {
    // Silent fail
  }
}

// Main hook logic
export default async function hook({ tool, parameters, result, error }) {
  // Only process successful memory-tool commands
  if (tool !== 'Bash' || error || !result?.stdout) return;

  const stdout = result.stdout;
  const command = parameters?.command || '';

  // Case 1: Detect memory-tool search output
  if (command.includes('memory-tool search')) {
    const match = stdout.match(/\[search_id:(\d+)\]/);
    if (match) {
      const search_id = parseInt(match[1]);
      // Start new search context
      saveSession({ search_id, used_ids: [] });
    }
  }

  // Case 2: Detect memory-tool get (memory being used)
  else if (command.match(/memory-tool get (\d+)/)) {
    const memIdMatch = command.match(/memory-tool get (\d+)/);
    if (memIdMatch) {
      const mem_id = parseInt(memIdMatch[1]);
      const session = loadSession();

      if (session.search_id && !session.used_ids.includes(mem_id)) {
        session.used_ids.push(mem_id);
        saveSession(session);
      }
    }
  }

  // Case 3: Detect memory-tool update/delete (also counts as "used")
  else if (command.match(/memory-tool (update|delete|tag|relate) (\d+)/)) {
    const memIdMatch = command.match(/memory-tool (?:update|delete|tag|relate) (\d+)/);
    if (memIdMatch) {
      const mem_id = parseInt(memIdMatch[1]);
      const session = loadSession();

      if (session.search_id && !session.used_ids.includes(mem_id)) {
        session.used_ids.push(mem_id);
        saveSession(session);
      }
    }
  }

  // Case 4: New search or session end → log accumulated feedback
  if (command.includes('memory-tool search') ||
      command.includes('memory-tool dream') ||
      command.includes('memory-tool snapshot')) {

    const session = loadSession();
    if (session.search_id && session.used_ids.length > 0) {
      // Log feedback before starting new search
      logFeedback(session.search_id, session.used_ids);
    }
  }
}

// Hook metadata
export const metadata = {
  name: 'search-feedback',
  description: 'Auto-logs search feedback when memories are accessed',
  version: '1.0.0',
  lifecycle: 'PostToolUse'
};
