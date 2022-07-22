import keyboard  # https://pypi.org/project/keyboard/
import platform


class Input:
    def __init__(self) -> None:
        self.receiving_input = True
        self.lines = []

    def get_lines(self) -> str:
        keyboard.add_hotkey("ctrl+enter", self._toggle_receiving_input)
        while self.receiving_input:
            self.lines.append(input())
        return "\n".join(self.lines)

    def _toggle_receiving_input(self) -> None:
        keyboard.write("\n")  # Some terminals require this for `input` to return.
        self.receiving_input = not self.receiving_input


def get_lines() -> str:
    print(end="\x1b[90m(")
    if platform.system().lower() == "windows":
        print(end="ctrl")
    else:
        print(end="cmd")
    print("+enter to submit)\x1b[39m")
    return Input().get_lines()
