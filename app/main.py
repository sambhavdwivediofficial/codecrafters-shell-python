import sys


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
            else:
                print(f"{cmd}: not found")
            continue

        print(f"{command}: command not found")


if __name__ == "__main__":
    main()