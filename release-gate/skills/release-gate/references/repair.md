# Repair Protocol Reference

This reference details the private protocol commands for executing a bounded, deterministic repair workflow.

## Overview

When the user explicitly invokes `/release-gate repair --base <ref>`, the skill orchestrates a safe, bounded repair loop using private `repair-*` commands. The source repository is never modified until final user approval.

## Protocol Commands

1. **Start**: Initialize session and evaluate initial candidate `C0`.
   ```text
   release-gate repair-start --repo <repo> --base <ref>
   ```
   Outputs:
   - `REPAIR_SESSION: <session_dir>`
   - `REPAIR_STATE: <state>`
   - `NEXT_ACTION: <action>`
   - `REPAIR_REQUEST: <approval_request_path>` (if awaiting approval)
   - `REPAIR_SUMMARY: <summary_path>`

2. **Approve Start**: Authorize editing within approved boundaries.
   ```text
   release-gate repair-approve --session <session_dir> --approval <approval_file>
   ```
   `<approval_file>` contains `{"session_id": "<session_id>"}`.

3. **Request Workspace**: Get current attempt instructions and workspace directory.
   ```text
   release-gate repair-request --session <session_dir>
   ```
   Outputs:
   - `WORKSPACE: <path>`
   - `APPROVED_PATHS: <paths>`
   - `FAILED_CHECKS: <checks>`

4. **Evaluate Attempt**: Export candidate, execute gate, and record lineage.
   ```text
   release-gate repair-evaluate --session <session_dir>
   ```
   Outputs:
   - `REPAIR_STATE: awaiting_final_approval | repairing | stopped`
   - `NEXT_ACTION: final_approval_and_apply | edit_workspace | none`

5. **Apply Final Patch**: Safely and transactionally patch the source worktree.
   ```text
   release-gate repair-apply --session <session_dir> --approval <final_approval_file>
   ```
   `<final_approval_file>` contains:
   ```json
   {
     "session_id": "<session_id>",
     "final_candidate_tree": "<tree_sha>",
     "final_patch_digest": "<patch_sha256>",
     "approved_at": "<utc_iso>"
   }
   ```

6. **Cancel Session**: Halt active session cleanly.
   ```text
   release-gate repair-cancel --session <session_dir>
   ```

## User Response Guidelines

- **Stopped**: "Repair stopped: <reason>."
- **Needs Approval**: "Repair requires your approval to modify: <approved_paths> (budget: 2 attempts)."
- **Ready to Apply**: "Repair passed all checks. Review final diff and approve to apply to source worktree."
