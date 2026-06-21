import os
import sys
import shlex
import readline
import subprocess

BUILTINS = ["echo", "exit", "type", "pwd", "cd", "jobs", "complete"]

tab_press_count = 0
last_completion_text = ""
COMPLETION_SPECS = {}

background_jobs = {}

def find_executables_starting_with(prefix):
    matches = []
    seen = set()
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    for path_dir in path_dirs:
        if not os.path.isdir(path_dir):
            continue
        try:
            for filename in os.listdir(path_dir):
                if filename.startswith(prefix):
                    full_path = os.path.join(path_dir, filename)
                    if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                        if filename not in seen:
                            matches.append(filename)
                            seen.add(filename)
        except (PermissionError, OSError):
            continue
    return sorted(matches)

def get_longest_common_prefix(strs):
    if not strs:
        return ""
    s1, s2 = min(strs), max(strs)
    for i, c in enumerate(s1):
        if i >= len(s2) or c != s2[i]:
            return s1[:i]
    return s1

def completer(text, state):
    global tab_press_count, last_completion_text
    line = readline.get_line_buffer()

    if " " in line:
        if state == 0:
            try:
                if "/" in text:
                    dirname, prefix = text.rsplit("/", 1)
                    search_dir = dirname if dirname else "/"
                else:
                    dirname, prefix = "", text
                    search_dir = "."

                if os.path.isdir(search_dir):
                    files = os.listdir(search_dir)
                    file_matches = sorted([f for f in files if f.startswith(prefix)])
                    
                    if len(file_matches) == 1:
                        tab_press_count = 0
                        full_match_path = os.path.join(dirname, file_matches[0]) if dirname else file_matches[0]
                        if os.path.isdir(os.path.join(search_dir, file_matches[0])):
                            return full_match_path + "/"
                        else:
                            return full_match_path + " "
                    
                    elif len(file_matches) > 1:
                        lcp = get_longest_common_prefix(file_matches)
                        if lcp and lcp != prefix:
                            tab_press_count = 0
                            return os.path.join(dirname, lcp) if dirname else lcp
                        
                        if line == last_completion_text:
                            tab_press_count += 1
                        else:
                            tab_press_count = 1
                            last_completion_text = line

                        if tab_press_count == 1:
                            sys.stdout.write("\x07")
                            sys.stdout.flush()
                            return None
                        elif tab_press_count >= 2:
                            display_matches = []
                            for m in file_matches:
                                if os.path.isdir(os.path.join(search_dir, m)):
                                    display_matches.append(m + "/")
                                else:
                                    display_matches.append(m)
                            sys.stdout.write("\n" + "  ".join(display_matches) + "\n")
                            sys.stdout.write("$ " + line)
                            sys.stdout.flush()
                            return None
                    else:
                        sys.stdout.write("\x07")
                        sys.stdout.flush()
            except Exception:
                pass
        return None

    builtin_matches = sorted([cmd for cmd in BUILTINS if cmd.startswith(text)])
    executable_matches = find_executables_starting_with(text)
    all_matches = builtin_matches + [cmd for cmd in executable_matches if cmd not in builtin_matches]
    all_matches = sorted(list(set(all_matches)))

    if not all_matches:
        if state == 0:
            sys.stdout.write("\x07")
            sys.stdout.flush()
        return None

    if len(all_matches) == 1:
        tab_press_count = 0
        if state == 0:
            return all_matches[0] + " "
        return None

    lcp = get_longest_common_prefix(all_matches)
    if lcp and lcp != text:
        tab_press_count = 0
        if state == 0:
            return lcp
        return None

    if state == 0:
        if line == last_completion_text:
            tab_press_count += 1
        else:
            tab_press_count = 1
            last_completion_text = line

        if tab_press_count == 1:
            sys.stdout.write("\x07")
            sys.stdout.flush()
            return None
        elif tab_press_count >= 2:
            sys.stdout.write("\n" + "  ".join(all_matches) + "\n")
            sys.stdout.write("$ " + line)
            sys.stdout.flush()
            return None
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
        procs = info["procs"]
        
        if info["status"] == "Running" and all(p.poll() is not None for p in procs):
            info["status"] = "Done"
            if info["command"].endswith(" &"):
                info["command"] = info["command"][:-2]
            reap_list.append(job_id)
            
            marker = " "
            if i == total_jobs - 1:
                marker = "+"
            elif i == total_jobs - 2:
                marker = "-"
                
            status_field = f"{info['status']}".ljust(24)
            print(f"[{job_id}]{marker}  {status_field}{info['command']}")
        elif print_running:
            marker = " "
            if i == total_jobs - 1:
                marker = "+"
            elif i == total_jobs - 2:
                marker = "-"
                
            status_field = f"{info['status']}".ljust(24)
            print(f"[{job_id}]{marker}  {status_field}{info['command']}")
            
    for job_id in reap_list:
        del background_jobs[job_id]

def setup_redirection(parts):
    stdout_file = None
    stderr_file = None
    stdout_mode = "w"
    stderr_mode = "w"

    if ">>" in parts:
        idx = parts.index(">>")
        stdout_file = parts[idx + 1]
        stdout_mode = "a"
        parts = parts[:idx]
    elif "1>>" in parts:
        idx = parts.index("1>>")
        stdout_file = parts[idx + 1]
        stdout_mode = "a"
        parts = parts[:idx]
    elif ">" in parts:
        idx = parts.index(">")
        stdout_file = parts[idx + 1]
        parts = parts[:idx]
    elif "1>" in parts:
        idx = parts.index("1>")
        stdout_file = parts[idx + 1]
        parts = parts[:idx]

    if "2>>" in parts:
        idx = parts.index("2>>")
        stderr_file = parts[idx + 1]
        stderr_mode = "a"
        parts = parts[:idx]
    elif "2>" in parts:
        idx = parts.index("2>")
        stderr_file = parts[idx + 1]
        stderr_mode = "w"
        parts = parts[:idx]

    if stderr_file and stderr_mode == "w":
        open(stderr_file, "w").close()

    return parts, stdout_file, stdout_mode, stderr_file, stderr_mode

def run_builtin(parts, stdout_file=None, stdout_mode="w"):
    output = ""
    if parts[0] == "echo":
        output = " ".join(parts[1:]) + "\n"
    elif parts[0] == "pwd":
        output = os.getcwd() + "\n"
    elif parts[0] == "type":
        cmd = parts[1] if len(parts) > 1 else ""
        if cmd in BUILTINS:
            output = f"{cmd} is a shell builtin\n"
        else:
            executable = find_executable(cmd)
            if executable:
                output = f"{cmd} is {executable}\n"
            else:
                output = f"{cmd}: not found\n"
    elif parts[0] == "complete":
        if len(parts) > 1:
            if parts[1] == "-p" and len(parts) > 2:
                cmd_arg = parts[2]
                if cmd_arg in COMPLETION_SPECS:
                    output = f"complete -C '{COMPLETION_SPECS[cmd_arg]}' {cmd_arg}\n"
                else:
                    output = f"complete: {cmd_arg}: no completion specification\n"
            elif parts[1] == "-C" and len(parts) > 3:
                script_path = parts[2]
                cmd_arg = parts[3]
                COMPLETION_SPECS[cmd_arg] = script_path
    elif parts[0] == "jobs":
        check_and_reap_jobs(print_running=True)
        return

    if stdout_file:
        with open(stdout_file, stdout_mode) as f:
            f.write(output)
    else:
        sys.stdout.write(output)
        sys.stdout.flush()

def main():
    while True:
        check_and_reap_jobs(print_running=False)
        
        sys.stdout.write("$ ")
        sys.stdout.flush()

        try:
            command = input()
        except EOFError:
            break

        if not command.strip():
            continue

        raw_command_string = command.strip()
        
        is_background = False
        if raw_command_string.endswith("&"):
            is_background = True
            raw_command_string = raw_command_string[:-1].strip()

        if "|" in raw_command_string:
            cmd_segments = raw_command_string.split("|", 1)
            parts1 = shlex.split(cmd_segments[0])
            parts2 = shlex.split(cmd_segments[1])

            parts1, stdout_file1, stdout_mode1, stderr_file1, stderr_mode1 = setup_redirection(parts1)
            parts2, stdout_file2, stdout_mode2, stderr_file2, stderr_mode2 = setup_redirection(parts2)

            is_builtin1 = parts1[0] in BUILTINS
            is_builtin2 = parts2[0] in BUILTINS

            exec1 = None if is_builtin1 else find_executable(parts1[0])
            exec2 = None if is_builtin2 else find_executable(parts2[0])

            if (is_builtin1 or exec1) and (is_builtin2 or exec2):
                try:
                    r, w = os.pipe()
                    
                    if is_builtin1:
                        pid1 = os.fork()
                        if pid1 == 0:
                            os.close(r)
                            os.dup2(w, sys.stdout.fileno())
                            os.close(w)
                            if stderr_file1:
                                stderr_target1 = open(stderr_file1, stderr_mode1)
                                os.dup2(stderr_target1.fileno(), sys.stderr.fileno())
                            run_builtin(parts1)
                            os._exit(0)
                        else:
                            proc1 = subprocess.Popen.__new__(subprocess.Popen)
                            proc1.returncode = None
                            proc1.pid = pid1
                            proc1._child_created = True
                            proc1.poll = lambda: subprocess._active.remove(proc1) if os.waitpid(pid1, os.WNOHANG) == (pid1, 0) else None
                            proc1.wait = lambda: os.waitpid(pid1, 0)
                    else:
                        stderr_target1 = open(stderr_file1, stderr_mode1) if stderr_file1 else None
                        proc1 = subprocess.Popen(
                            parts1,
                            executable=exec1,
                            stdout=w,
                            stderr=stderr_target1
                        )
                    os.close(w)

                    if is_builtin2:
                        pid2 = os.fork()
                        if pid2 == 0:
                            os.dup2(r, sys.stdin.fileno())
                            os.close(r)
                            if stdout_file2:
                                stdout_target2 = open(stdout_file2, stdout_mode2)
                                os.dup2(stdout_target2.fileno(), sys.stdout.fileno())
                            if stderr_file2:
                                stderr_target2 = open(stderr_file2, stderr_mode2)
                                os.dup2(stderr_target2.fileno(), sys.stderr.fileno())
                            run_builtin(parts2)
                            os._exit(0)
                        else:
                            proc2 = subprocess.Popen.__new__(subprocess.Popen)
                            proc2.returncode = None
                            proc2.pid = pid2
                            proc2._child_created = True
                            proc2.poll = lambda: subprocess._active.remove(proc2) if os.waitpid(pid2, os.WNOHANG) == (pid2, 0) else None
                            proc2.wait = lambda: os.waitpid(pid2, 0)
                    else:
                        stdout_target2 = open(stdout_file2, stdout_mode2) if stdout_file2 else None
                        stderr_target2 = open(stderr_file2, stderr_mode2) if stderr_file2 else None
                        proc2 = subprocess.Popen(
                            parts2,
                            executable=exec2,
                            stdin=r,
                            stdout=stdout_target2,
                            stderr=stderr_target2
                        )
                    os.close(r)

                    if is_background:
                        current_job_id = 1 if not background_jobs else max(background_jobs.keys()) + 1
                        print(f"[{current_job_id}] {proc2.pid}")
                        background_jobs[current_job_id] = {
                            "procs": [proc1, proc2],
                            "command": command.strip(),
                            "status": "Running"
                        }
                    else:
                        proc1.wait()
                        proc2.wait()
                        if not is_builtin2:
                            if stdout_target2: stdout_target2.close()
                            if stderr_target2: stderr_target2.close()
                        if not is_builtin1:
                            if stderr_target1: stderr_target1.close()
                except Exception:
                    pass
            else:
                if not is_builtin1 and not exec1:
                    print(f"{parts1[0]}: command not found")
                if not is_builtin2 and not exec2:
                    print(f"{parts2[0]}: command not found")
            continue

        parts = shlex.split(raw_command_string)
        parts, stdout_file, stdout_mode, stderr_file, stderr_mode = setup_redirection(parts)

        if not parts:
            continue

        if parts[0] == "exit":
            break

        if parts[0] == "cd":
            directory = parts[1] if len(parts) > 1 else "~"
            if directory == "~":
                os.chdir(os.environ["HOME"])
            elif os.path.isdir(directory):
                os.chdir(directory)
            else:
                print(f"cd: {directory}: No such file or directory")
            continue

        if parts[0] in BUILTINS:
            run_builtin(parts, stdout_file, stdout_mode)
            continue

        executable = find_executable(parts[0])
        if executable:
            stdout_target = open(stdout_file, stdout_mode) if stdout_file else None
            stderr_target = open(stderr_file, stderr_mode) if stderr_file else None
            try:
                if is_background:
                    current_job_id = 1 if not background_jobs else max(background_jobs.keys()) + 1
                    proc = subprocess.Popen(
                        parts,
                        executable=executable,
                        stdout=stdout_target,
                        stderr=stderr_target
                    )
                    print(f"[{current_job_id}] {proc.pid}")
                    background_jobs[current_job_id] = {
                        "procs": [proc],
                        "command": command.strip(),
                        "status": "Running"
                    }
                else:
                    subprocess.run(
                        parts,
                        executable=executable,
                        stdout=stdout_target,
                        stderr=stderr_target
                    )
            except Exception:
                pass
            finally:
                if not is_background:
                    if stdout_target:
                        stdout_target.close()
                    if stderr_target:
                        stderr_target.close()
        else:
            print(f"{parts[0]}: command not found")

if __name__ == "__main__":
    main()
    