import sys
import os
import subprocess


def find_executable(cmd):
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        full_path = os.path.join(path_dir, cmd)

        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            return full_path

    return None


def main():
    builtins = ["echo", "exit", "type"]

    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()

        command = input()
        parts = command.split()

        if not parts:
            continue

        if command == "exit":
            break

        if parts[0] == "echo":
            print(" ".join(parts[1:]))
            continue

        if parts[0] == "type":
            cmd = parts[1]

            if cmd in builtins:
                print(f"{cmd} is a shell builtin")
            else:
                executable = find_executable(cmd)

                if executable:
                    print(f"{cmd} is {executable}")
                else:
                    print(f"{cmd}: not found")

            continue

        executable = find_executable(parts[0])

        if executable:
            subprocess.run(
                [parts[0]] + parts[1:],
                executable=executable
            )
        else:
            print(f"{command}: command not found")


if __name__ == "__main__":
    main()