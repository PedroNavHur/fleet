## This machine: the MacBook

The MacBook has 10 cores (4 performance, 6 efficiency) and 16 GiB of RAM, and
is Pedro's interactive machine.

- Limits: 3 jobs, 2 heavy, 1 build. Vitest defaults to 4 workers.
- macOS has no cgroups, so there is no slice. Each job runs under
  `taskpolicy -c utility`, a QoS clamp that every child process inherits:
  queued jobs use idle CPU at full speed but yield almost all of it to
  interactive work. Work handed to an already-running process (Docker Desktop's
  VM, a dev server, build daemons, the editor's TypeScript server) keeps that
  process's priority.
- host-check does not limit memory on this machine.
- Development servers are allowed.
- `bg-job` runs each job detached in its own session under `caffeinate -i`, so
  the Mac does not idle-sleep mid-job. Closing the lid still pauses it.
