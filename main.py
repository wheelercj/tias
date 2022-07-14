import aiohttp  # https://docs.aiohttp.org/en/stable/
import async_tio  # https://pypi.org/project/async-tio/
import asyncio
import json
import keyboard  # https://pypi.org/project/keyboard/
import platform
from textwrap import dedent
from typing import List
from typing import Tuple


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(amain(loop))


async def amain(loop):
    async with aiohttp.ClientSession(loop=loop) as session:
        file_name = "valid_languages.json"
        languages, aliases = await get_languages(loop, session, file_name)
        chosen_language = input("\x1b[32mlanguage: \x1b[39m").lower().strip()
        if chosen_language.endswith(" jargon"):
            chosen_language = chosen_language[: -len(" jargon")].strip()
            if chosen_language not in languages:
                raise ValueError(f"Invalid language: `{chosen_language}`")
            await print_jargon(chosen_language)
        elif chosen_language.startswith("list"):
            filter_prefix = ""
            if len(chosen_language) > len("list"):
                filter_prefix = chosen_language[len("list") :].strip()
            await list_languages(languages, aliases, filter_prefix)
        else:
            if chosen_language not in languages:
                raise ValueError(f"Invalid language: `{chosen_language}`")
            chosen_language, code, inputs = await get_code(chosen_language)
            await run_code(
                loop,
                session,
                file_name,
                languages,
                aliases,
                chosen_language,
                code,
                inputs,
            )


async def get_languages(loop, session, file_name: str) -> Tuple[List[str], List[str]]:
    aliases = [
        "c",
        "c#",
        "c++",
        "cpp",
        "cs",
        "f#",
        "fs",
        "java",
        "javascript",
        "js",
        "objective-c",
        "py",
        "python",
        "swift",
    ]
    file_exists = True
    try:
        with open(file_name, "r", encoding="utf8") as file:
            languages = json.load(file)
            for alias in aliases:
                if alias not in languages:
                    languages.append(alias)
            return languages, aliases
    except FileNotFoundError:
        file_exists = False
    async with await async_tio.Tio(loop=loop, session=session) as tio:
        languages = tio.languages
        languages.extend(aliases)
        if not file_exists:
            await save_languages(file_name, languages)
        return languages, aliases


async def save_languages(file_name: str, languages: List[str]) -> None:
    with open(file_name, "w", encoding="utf8") as file:
        json.dump(languages, file)


async def print_jargon(language: str) -> None:
    """Shows the jargon for a language, if it has jargon."""
    if language in ("c", "c-clang"):
        print(get_c_jargon_header())
    elif language in ("c++", "cpp", "cpp-clang"):
        print(get_cpp_jargon_header())
    elif language in ("c#", "cs", "cs-csc"):
        print(get_cs_jargon_header())
    elif language == "dart":
        print(get_dart_jargon_header())
    elif language == "go":
        print(get_go_jargon_header())
    elif language in ("java", "java-openjdk"):
        print(get_java_jargon_header())
    elif language == "kotlin":
        print(get_kotlin_jargon_header())
    elif language.startswith("objective-c"):
        print(get_objective_c_jargon_header())
    elif language == "rust":
        print(get_rust_jargon_header())
    elif language == "scala":
        print(get_scala_jargon_header())
    else:
        raise ValueError(
            f"No jargon wrapping has been set for the `{language}` language"
        )


async def list_languages(
    valid_languages: List[str], aliases: List[str], filter_prefix: str
) -> None:
    """Lists supported languages, optionally filtered by a prefix."""
    if filter_prefix:
        valid_languages = list(
            filter(lambda s: s.startswith(filter_prefix), valid_languages)
        )
        lang_count = len(valid_languages)
        print(
            f"languages that start with `{filter_prefix}` ({lang_count}): ",
            end="",
        )
    else:
        print(f"languages ({len(valid_languages) - len(aliases)}): ", end="")
    valid_languages = sorted(valid_languages)
    valid_languages = ", ".join(valid_languages)
    print(valid_languages)


async def get_code(chosen_language: str) -> Tuple[str, str, str]:
    print(end="\x1b[32mcode: \x1b[90m(")
    if platform == "darwin":
        print(end="cmd")
    else:
        print(end="ctrl")
    print("+enter to run)\x1b[39m")
    code: str = Input().get_code()
    inputs = ""
    if "```" in code:
        _, code, inputs = await unwrap_code_block(code)
    chosen_language, code = await parse_exec_language(chosen_language, code)
    return chosen_language, code, inputs


async def run_code(
    loop,
    session,
    file_name: str,
    languages: List[str],
    aliases: List[str],
    chosen_language: str,
    code: str,
    inputs: str,
) -> None:
    async with await async_tio.Tio(loop=loop, session=session) as tio:
        if len(languages) - len(aliases) != len(tio.languages):
            languages = tio.languages
            languages.extend(aliases)
            await save_languages(file_name, languages)
        response = await tio.execute(code, language=chosen_language, inputs=inputs)
    print(f"\x1b[32m`{chosen_language}` output:\x1b[39m\n{response.stdout}", end="")
    if not response.stdout.endswith("\n"):
        print()
    print(f"\x1b[32mexit status: \x1b[39m{response.exit_status}")


class Input:
    def __init__(self) -> None:
        self.receiving_input = True
        self.lines = []

    def get_code(self) -> str:
        keyboard.add_hotkey("ctrl+enter", self._toggle_receiving_input)
        while self.receiving_input:
            self.lines.append(input())
        return "\n".join(self.lines)

    def _toggle_receiving_input(self) -> None:
        keyboard.write("\n")  # Some terminals require this for the `input` call to end.
        self.receiving_input = not self.receiving_input


async def unwrap_code_block(statement: str) -> Tuple[str, str, str]:
    """Removes triple backticks and a syntax name around a code block.

    Returns any syntax name found, the unwrapped code, and anything after
    closing triple backticks. Any syntax name must be on the same line as the
    leading triple backticks, and code must be on the next line(s). If there
    are not triple backticks, the returns are 'txt' and the unchanged input. If
    there are triple backticks and no syntax is specified, the first two
    returns will be 'txt' and the unwrapped code block. If there is nothing
    after the closing triple backticks, the third returned value will be an
    empty string. The result is not dedented. Closing triple backticks are
    optional (unless something is needed after them).
    """
    syntax = "txt"
    if not statement.startswith("```"):
        return syntax, statement, ""
    statement = statement[3:]
    # Find the syntax name if one is given.
    i = statement.find("\n")
    if i != -1:
        first_line = statement[:i].strip()
        if len(first_line):
            syntax = first_line
            statement = statement[i:]
    if statement.startswith("\n"):
        statement = statement[1:]
    suffix = ""
    if "```" in statement:
        statement, suffix = statement.split("```", 1)
    if statement.endswith("\n"):
        statement = statement[:-1]
    return syntax, statement, suffix


async def parse_exec_language(language: str, expression: str) -> Tuple[str, str]:
    """Changes some language names for TIO and can wrap jargon."""
    if language == "c" or language.startswith("c-"):
        if language == "c":
            language = "c-clang"
        if "int main(" not in expression:
            expression = wrap_with_c_jargon(expression)
    elif language in ("cpp", "c++") or language.startswith("cpp-"):
        if language in ("cpp", "c++"):
            language = "cpp-clang"
        if "int main(" not in expression:
            expression = wrap_with_cpp_jargon(expression)
    elif language in ("cs", "c#") or language.startswith("cs-"):
        if language in ("cs", "c#"):
            language = "cs-csc"
        if "static void Main(" not in expression:
            expression = wrap_with_cs_jargon(expression)
    elif language == "dart":
        if "void main(" not in expression:
            expression = wrap_with_dart_jargon(expression)
    elif language in ("fs", "f#"):
        language = "fs-core"
    elif language == "go":
        if "func main(" not in expression:
            expression = wrap_with_go_jargon(expression)
    elif language == "java" or language.startswith("java-"):
        if language == "java":
            language = "java-openjdk"
        if "public static void main(" not in expression:
            expression = wrap_with_java_jargon(expression)
    elif language == "js":
        language = "javascript-node"
    elif language == "kotlin":
        if "fun main(" not in expression:
            expression = wrap_with_kotlin_jargon(expression)
    elif language.startswith("objective-c"):
        if language == "objective-c":
            language = "objective-c-clang"
        if "int main(" not in expression:
            expression = wrap_with_objective_c_jargon(expression)
    elif language in ("py", "python", "txt"):
        language = "python3"
    elif language == "rust":
        if "fn main(" not in expression:
            expression = wrap_with_rust_jargon(expression)
    elif language == "scala":
        if "object Main" not in expression:
            expression = wrap_with_scala_jargon(expression)
    elif language == "swift":
        language = "swift4"

    return language, expression


def wrap_with_c_jargon(expression: str) -> str:
    return get_c_jargon_header() + expression + "}"


def wrap_with_cpp_jargon(expression: str) -> str:
    return get_cpp_jargon_header() + expression + "}"


def wrap_with_cs_jargon(expression: str) -> str:
    return get_cs_jargon_header() + expression + "}}}"


def wrap_with_dart_jargon(expression: str) -> str:
    return get_dart_jargon_header() + expression + "}"


def wrap_with_go_jargon(expression: str) -> str:
    return get_go_jargon_header() + expression + "}"


def wrap_with_java_jargon(expression: str) -> str:
    return get_java_jargon_header() + expression + "}}"


def wrap_with_kotlin_jargon(expression: str) -> str:
    return get_kotlin_jargon_header() + expression + "}"


def wrap_with_objective_c_jargon(expression: str) -> str:
    return get_objective_c_jargon_header() + expression + "}"


def wrap_with_rust_jargon(expression: str) -> str:
    return get_rust_jargon_header() + expression + "}"


def wrap_with_scala_jargon(expression: str) -> str:
    return get_scala_jargon_header() + expression + "}"


def get_c_jargon_header() -> str:
    return dedent(
        """
        #include <ctype.h>
        #include <math.h>
        #include <stdbool.h>
        #include <stdio.h>
        #include <stdlib.h>
        #include <string.h>
        #include <time.h>

        int main(void) {
        """
    )


def get_cpp_jargon_header() -> str:
    return dedent(
        """
        #include <algorithm>
        #include <cctype>
        #include <cstring>
        #include <ctime>
        #include <fstream>
        #include <iomanip>
        #include <iostream>
        #include <math.h>
        #include <numeric>
        #include <sstream>
        #include <stdio.h>
        #include <string>
        #include <vector>
        using namespace std;

        int main() {
        """
    )


def get_cs_jargon_header() -> str:
    return dedent(
        """
        namespace MyNamespace {
            class MyClass {         
                static void Main(string[] args) {
        """
    )


def get_dart_jargon_header() -> str:
    return "void main() {"


def get_go_jargon_header() -> str:
    return dedent(
        """
        package main
        import "fmt"

        func main() {
        """
    )


def get_java_jargon_header() -> str:
    return dedent(
        """
        import java.util.*;

        class MyClass {
            public static void main(String[] args) {
                Scanner scanner = new Scanner(System.in);
        """
    )


def get_kotlin_jargon_header() -> str:
    return "fun main(args : Array<String>) {"


def get_objective_c_jargon_header() -> str:
    return dedent(
        """
        #include <stdio.h>
        // Print with the `puts` function, not `NSLog`.
        
        int main() {
        """
    )


def get_rust_jargon_header() -> str:
    return "fn main() {"


def get_scala_jargon_header() -> str:
    return "object Main extends App {"


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt")
    except ValueError as e:
        print(e)
