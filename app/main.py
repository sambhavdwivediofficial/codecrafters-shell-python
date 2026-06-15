import os
import sys
import shlex
import readline
import subprocess

BUILTINS = ["echo", "exit", "type", "pwd", "cd"]


def find_executables_starting_with(prefix):
    """Find all executables in PATH that start with the given prefix."""
    matches = []
    seen = set()
    
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    
    for path_dir in path_dirs:
        # Handle non-existent directories gracefully
        if not os.path.isdir(path_dir):
            continue
        
        try:
            for filename in os.listdir(path_dir):
                if filename.startswith(prefix):
                    full_path = os.path.join(path_dir, filename)
                    # Check if it's a file and executable
                    if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                        if filename not in seen:
                            matches.append(filename)
                            seen.add(filename)
        except (PermissionError, OSError):
            # Handle permission errors or other OS errors gracefully
            continue
    
    return sorted(matches)


def completer(text, state):
    line = readline.get_line_buffer()

    if " " in line:
        return None

    # Get matches from builtins and external executables
    builtin_matches = [cmd for cmd in BUILTINS if cmd.startswith(text)]
    executable_matches = find_executables_starting_with(text)
    
    # Combine matches, prioritizing builtins
    all_matches = builtin_matches + [cmd for cmd in executable_matches if cmd not in builtin_matches]

    # If there are multiple matches and this is the first state
    if len(all_matches) > 1 and state == 0:
        sys.stdout.write("\x07")
        sys.stdout.flush()
        return None

    # If there's exactly one match, complete it
    if state < len(all_matches):
        return all_matches[state] + " "

    # If no matches found and this is the first state, ring the bell
    if state == 0 and len(all_matches) == 0:
        sys.stdout.write("\x07")
        sys.stdout.flush()

    return None


def display_matches(substitution, matches, longest_match_length):
    """Display all matching completions."""
    print()
    print("  ".join(matches))
    sys.stdout.write("$ " + substitution)
    sys.stdout.flush()


readline.set_completer(completer)
readline.set_completion_display_matches_hook(display_matches)
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
            finally:
                if stdout_target:
                    stdout_target.close()
                if stderr_target:
                    stderr_target.close()
        else:
            print(f"{parts[0]}: command not found")


if __name__ == "__main__":
    main()