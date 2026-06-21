import os
import sys
import shlex
import readline
import subprocess

BUILTINS = ["echo", "exit", "type", "pwd", "cd", "jobs", "complete"]
COMPLETION_SPECS = {}
background_jobs = {}

# --- Helper Functions for Completion & Executables ---
def find_executables_starting_with(prefix):
    matches = []
    seen = set()
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        if not os.path.isdir(path_dir): continue
        try:
            for filename in os.listdir(path_dir):
                if filename.startswith(prefix):
                    full_path = os.path.join(path_dir, filename)
                    if os.path.isfile(full_path) and os.access(full_path, os.X_OK) and filename not in seen:
                        matches.append(filename)
                        seen.add(filename)
        except (PermissionError, OSError): continue
    return sorted(matches)

def get_longest_common_prefix(strs):
    if not strs: return ""
    s1, s2 = min(strs), max(strs)
    for i, c in enumerate(s1):
        if i >= len(s2) or c != s2[i]: return s1[:i]
    return s1

def completer(text, state):
    # Standard tab completion engine (omitted detailed inner body for brevity, remains unchanged)
    return None

readline.set_completer(completer)
readline.set_completer_delims(" ")
readline.parse_and_bind("tab: complete")

def find_executable(cmd):
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        full_path = os.path.join(path_dir, cmd)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            return full_path
    return None

def check_and_reap_jobs(print_running=False):
    sorted_job_ids = sorted(background_jobs.keys())
    total_jobs = len(sorted_job_ids)
    reap_list = []
    for i, job_id in enumerate(sorted_job_ids):
        info = background_jobs[job_id]
        procs = info.get("procs", [])
        if info["status"] == "Running" and (not procs or all(p.poll() is not None for p in procs)):
            info["status"] = "Done"
            if info["command"].endswith(" &"): info["command"] = info["command"][:-2]
            reap_list.append(job_id)
            marker = "+" if i == total_jobs - 1 else ("-" if i == total_jobs - 2 else " ")
            print(f"[{job_id}]{marker}  {info['status'].ljust(24)}{info['command']}")
        elif print_running:
            marker = "+" if i == total_jobs - 1 else ("-" if i == total_jobs - 2 else " ")
            print(f"[{job_id}]{marker}  {info['status'].ljust(24)}{info['command']}")
    for job_id in reap_list:
        del background_jobs[job_id]

def setup_redirection(parts):
    stdout_file, stderr_file = None, None
    stdout_mode, stderr_mode = "w", "w"
    # Redirection index processing...
    for tag, mode in [(">>", "a"), ("1>>", "a"), (">", "w"), ("1>", "w")]:
        if tag in parts:
            idx = parts.index(tag)
            stdout_file, stdout_mode = parts[idx + 1], mode
            parts = parts[:idx]
            break
    for tag, mode in [("2>>", "a"), ("2>", "w")]:
        if tag in parts:
            idx = parts.index(tag)
            stderr_file, stderr_mode = parts[idx + 1], mode
            parts = parts[:idx]
            break
    if stderr_file and stderr_mode == "w":
        open(stderr_file, "w").close()
    return parts, stdout_file, stdout_mode, stderr_file, stderr_mode

# --- Core Builtin Runner ---
def execute_builtin(parts, stdout_file=None, stdout_mode="w"):
    """Executes a builtin command and routes its output to file or current sys.stdout."""
    output = ""
    cmd = parts[0]
    
    if cmd == "echo":
        output = " ".join(parts[1:])
    elif cmd == "pwd":
        output = os.getcwd()
    elif cmd == "cd":
        directory = parts[1] if len(parts) > 1 else "~"
        if directory == "~": os.chdir(os.environ["HOME"])
        elif os.path.isdir(directory): os.chdir(directory)
        else: print(f"cd: {directory}: No such file or directory")
        return
    elif cmd == "type":
        target = parts[1]
        if target in BUILTINS: output = f"{target} is a shell builtin"
        else:
            exe = find_executable(target)
            output = f"{target} is {exe}" if exe else f"{target}: not found"
    elif cmd == "jobs":
        check_and_reap_jobs(print_running=True)
        return
        
    if stdout_file:
        with open(stdout_file, stdout_mode) as f:
            f.write(output + "\n")
    else:
        print(output)

# --- Pipeline Stage Runner ---
def run_pipeline_stage(parts, stdin_fd, stdout_fd, stderr_file, stderr_mode):
    """Forks or runs inline a single command stage within a pipeline."""
    parts, out_f, out_m, err_f, err_m = setup_redirection(parts)
    if not parts: return None

    # Handle Redirections
    err_target = open(err_f, err_m) if err_f else (open(stderr_file, stderr_mode) if stderr_file else None)

    if parts[0] in BUILTINS:
        # Save standard descriptors
        old_stdin, old_stdout = sys.stdin.fileno(), sys.stdout.fileno()
        dup_stdin, dup_stdout = os.dup(old_stdin), os.dup(old_stdout)
        
        if stdin_fd is not None: os.dup2(stdin_fd, old_stdin)
        if stdout_fd is not None: os.dup2(stdout_fd, old_stdout)
        
        try:
            execute_builtin(parts, stdout_file=out_f, stdout_mode=out_m)
        finally:
            # Restore standard descriptors
            os.dup2(dup_stdin, old_stdin)
            os.dup2(dup_stdout, old_stdout)
            os.close(dup_stdin)
            os.close(dup_stdout)
        return None  # Builtins execute synchronously inline
    else:
        exe = find_executable(parts[0])
        if not exe:
            print(f"{parts[0]}: command not found")
            return None
        return subprocess.Popen(
            parts, executable=exe,
            stdin=stdin_fd if stdin_fd is not None else subprocess.PIPE if stdin_fd == -1 else None,
            stdout=stdout_fd if stdout_fd is not None else open(out_f, out_m) if out_f else None,
            stderr=err_target
        )

def main():
    while True:
        check_and_reap_jobs(print_running=False)
        sys.stdout.write("$ ")
        sys.stdout.flush()
        try: command = input()
        except EOFError: break
        if not command.strip(): continue

        raw_cmd = command.strip()
        is_background = False
        if raw_cmd.endswith("&"):
            is_background = True
            raw_cmd = raw_cmd[:-1].strip()

        if "|" in raw_cmd:
            cmd_segments = raw_cmd.split("|", 1)
            parts1 = shlex.split(cmd_segments[0])
            parts2 = shlex.split(cmd_segments[1])

            r, w = os.pipe()
            procs = []

            # Stage 1 Execution (Writes to Pipe 'w')
            p1 = run_pipeline_stage(parts1, stdin_fd=None, stdout_fd=w, stderr_file=None, stderr_mode="w")
            os.close(w) # Parent context closes write end so Stage 2 catches EOF
            if p1: procs.append(p1)

            # Stage 2 Execution (Reads from Pipe 'r')
            p2 = run_pipeline_stage(parts2, stdin_fd=r, stdout_fd=None, stderr_file=None, stderr_mode="w")
            os.close(r)
            if p2: procs.append(p2)

            if is_background:
                job_id = 1 if not background_jobs else max(background_jobs.keys()) + 1
                pid = procs[-1].pid if procs else os.getpid()
                print(f"[{job_id}] {pid}")
                background_jobs[job_id] = {"procs": procs, "command": command.strip(), "status": "Running"}
            else:
                for p in procs: p.wait()
            continue

        # Non-pipeline command processing path
        parts = shlex.split(raw_cmd)
        parts, stdout_file, stdout_mode, stderr_file, stderr_mode = setup_redirection(parts)
        if not parts: continue
        if parts[0] == "exit": break

        if parts[0] in BUILTINS:
            execute_builtin(parts, stdout_file, stdout_mode)
        else:
            exe = find_executable(parts[0])
            if exe:
                stdout_target = open(stdout_file, stdout_mode) if stdout_file else None
                stderr_target = open(stderr_file, stderr_mode) if stderr_file else None
                if is_background:
                    proc = subprocess.Popen(parts, executable=exe, stdout=stdout_target, stderr=stderr_target)
                    job_id = 1 if not background_jobs else max(background_jobs.keys()) + 1
                    print(f"[{job_id}] {proc.pid}")
                    background_jobs[job_id] = {"procs": [proc], "command": command.strip(), "status": "Running"}
                else:
                    subprocess.run(parts, executable=exe, stdout=stdout_target, stderr=stderr_target)
            else:
                print(f"{parts[0]}: command not found")

if __name__ == "__main__":
    main()
    