import sys
import os
import subprocess
import shlex


def find_executable(cmd):
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        full_path = os.path.join(path_dir, cmd)

        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            return full_path

    return None


def main():
    builtins = ["echo", "exit", "type", "pwd", "cd"]

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

        if ">" in parts:
            idx = parts.index(">")
            stdout_file = parts[idx + 1]
            parts = parts[:idx]
        elif "1>" in parts:
            idx = parts.index("1>")
            stdout_file = parts[idx + 1]
            parts = parts[:idx]

        if "2>" in parts:
            idx = parts.index("2>")
            stderr_file = parts[idx + 1]
            parts = parts[:idx]

        if stderr_file:
            open(stderr_file, "w").close()

        if not parts:
            continue

        if parts[0] == "exit":
            break

        if parts[0] == "echo":
            output = " ".join(parts[1:])

            if stdout_file:
                with open(stdout_file, "w") as f:
                    f.write(output + "\n")
            else:
                print(output)

            continue

        if parts[0] == "pwd":
            output = os.getcwd()

            if stdout_file:
                with open(stdout_file, "w") as f:
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

            if cmd in builtins:
                output = f"{cmd} is a shell builtin"
            else:
                executable = find_executable(cmd)

                if executable:
                    output = f"{cmd} is {executable}"
                else:
                    output = f"{cmd}: not found"

            if stdout_file:
                with open(stdout_file, "w") as f:
                    f.write(output + "\n")
            else:
                print(output)

            continue

        executable = find_executable(parts[0])

        if executable:
            stdout_target = open(stdout_file, "w") if stdout_file else None
            stderr_target = open(stderr_file, "w") if stderr_file else None

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