// OpenCode plugin: run shell commands past the host-check guard.
// bin/sync links this to ~/.config/opencode/plugins/host-check.js.
import { spawnSync } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

const GUARD = join(homedir(), ".local/lib/host-check/guard.py");

export const HostCheck = async () => ({
  "tool.execute.before": async (input, output) => {
    if (input.tool !== "bash") return;
    const result = spawnSync("/usr/bin/python3", [GUARD, "opencode"], {
      input: JSON.stringify({ command: output.args.command }),
      encoding: "utf8",
      timeout: 5000,
    });
    if (result.error || result.status !== 0) {
      throw new Error(result.stderr?.trim() || `Host validation guard failed; inspect ${GUARD}.`);
    }
  },
});
