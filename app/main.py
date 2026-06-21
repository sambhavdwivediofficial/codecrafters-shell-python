import os
import sys
import shlex
import readline
import subprocess

BUILTINS = ["echo", "exit", "type", "pwd", "cd"]

tab_press_count = 0
last_completion_text = ""

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

def main():
    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()

        try:
            command = input()
        except EOFError:
            break

        if not command.strip():
            continue

        parts = shlex.split(command)
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

        if not parts:
            continue

        if parts[0] == "exit":
            break

        if parts[0] == "echo":
            output = " ".join(parts[1:])
            if stdout_file:
                with open(stdout_file, stdout_mode) as f:
                    f.write(output + "\n")
            else:
                print(output)
            continue

        if parts[0] == "pwd":
            output = os.getcwd()
            if stdout_file:
                with open(stdout_file, stdout_mode) as f:
                    f.write(output + "\n")
            else:
                print(output)
            continue

        if parts[0] == "cd":
            directory = parts[1]
            if directory == "~":
                os.chdir(os.environ["HOME"])
            elif os.path.isdir(directory):
                os.chdir(directory)
            else:
                print(f"cd: {directory}: No such file or directory")
            continue

        if parts[0] == "type":
            cmd = parts[1]
            if cmd in BUILTINS:
                output = f"{cmd} is a shell builtin"
            else:
                executable = find_executable(cmd)
                if executable:
                    output = f"{cmd} is {executable}"
                else:
                    output = f"{cmd}: not found"

            if stdout_file:
                with open(stdout_file, stdout_mode) as f:
                    f.write(output + "\n")
            else:
                print(output)
            continue

        executable = find_executable(parts[0])
        if executable:
            stdout_target = open(stdout_file, stdout_mode) if stdout_file else None
            stderr_target = open(stderr_file, stderr_mode) if stderr_file else None
            try:
                subprocess.run(
                    parts,
                    executable=executable,
                    stdout=stdout_target,
                    stderr=stderr_target
                )
            except Exception:
                pass
            finally:
                if stdout_target:
                    stdout_target.close()
                if stderr_target:
                    stderr_target.close()
        else:
            print(f"{parts[0]}: command not found")

if __name__ == "__main__":
    main()
    