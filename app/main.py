import sys
import os


def main():
    builtins = ["echo", "exit", "type"]

    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()

        command = input()

        if command == "exit":
            break

        if command.startswith("echo "):
            print(command[5:])
            continue

        if command.startswith("type "):
            cmd = command[5:]

            if cmd in builtins:
                print(f"{cmd} is a shell builtin")
                continue

            found = False
            for path_dir in os.environ.get("PATH", "").split(os.pathsep):
                full_path = os.path.join(path_dir, cmd)

                if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                    print(f"{cmd} is {full_path}")
                    found = True
                    break

            if not found:
                print(f"{cmd}: not found")

            continue

        print(f"{command}: command not found")


if __name__ == "__main__":
    main()