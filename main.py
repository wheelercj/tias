import aiohttp  # https://docs.aiohttp.org/en/stable/
import async_tio  # https://pypi.org/project/async-tio/
import asyncio
import json
from textwrap import dedent
from typing import Tuple, List


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(amain(loop))


async def amain(loop):
    async with aiohttp.ClientSession(loop=loop) as session:
        file_name = "valid_languages.json"
        languages = await get_languages(loop, session, file_name)
        language = input("\x1b[32mlanguage: \x1b[39m").lower().strip()
        if language.endswith(" jargon"):
            language = language[: -len(" jargon")].strip()
            if language not in languages:
                raise ValueError(f"Invalid language: `{language}`")
            await print_jargon(language)
        elif language.startswith("list"):
            filter_prefix = ""
            if len(language) > len("list"):
                filter_prefix = language[len("list") :].strip()
            await list_languages(languages, filter_prefix)
        else:
            if language not in languages:
                raise ValueError(f"Invalid language: `{language}`")
            await get_and_run_code(loop, session, file_name, languages, language)


async def get_languages(loop, session, file_name: str) -> List[str]:
    file_exists = True
    try:
        with open(file_name, "r", encoding="utf8") as file:
            return json.load(file)
    except FileNotFoundError:
        file_exists = False
    async with await async_tio.Tio(loop=loop, session=session) as tio:
        languages = tio.languages
        aliases = [
            "c",
            "c#",
            "c++",
            "cpp",
            "cs",
            "java",
            "javascript",
            "js",
            "py",
            "python",
            "swift",
        ]
        languages.extend(aliases)
        if not file_exists:
            await save_languages(file_name, languages)
        return languages


async def save_languages(file_name: str, languages: List[str]) -> None:
    with open(file_name, "w", encoding="utf8") as file:
        json.dump(languages, file)


async def print_jargon(language: str) -> None:
    """Shows the jargon for a language, if it has jargon."""
    if language in ("c++", "cpp"):
        print(get_cpp_jargon_header())
    elif language == "c":
        print(get_c_jargon_header())
    elif language == "java":
        print(get_java_jargon_header())
    elif language in ("c#", "cs"):
        print(get_cs_jargon_header())
    else:
        raise ValueError(
            f"No jargon wrapping has been set for the `{language}` language"
        )


async def list_languages(valid_languages: List[str], filter_prefix: str) -> None:
    """Lists supported languages, optionally filtered by a prefix.

    You can also see a full list of supported languages here: https://tio.run/#
    """
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
        print(f"languages ({len(valid_languages)}): ", end="")
    valid_languages = sorted(valid_languages)
    valid_languages = ", ".join(valid_languages)
    print(valid_languages)


async def get_and_run_code(
    loop, session, file_name: str, languages: List[str], language: str
) -> None:
    print("\x1b[32mcode: \x1b[90m(enter an empty line to run)\x1b[39m")
    code: str = Input().get_code()
    inputs = ""
    if "```" in code:
        _, code, inputs = unwrap_code_block(code)
    language, code = parse_exec_language(language, code)
    async with await async_tio.Tio(loop=loop, session=session) as tio:
        if len(languages) != len(tio.languages):
            await save_languages(file_name, tio.languages)
        response = await tio.execute(code, language=language, inputs=inputs)
    print(f"\x1b[32m`{language}` output:\x1b[39m\n{response.stdout}", end="")
    if not response.stdout.endswith("\n"):
        print()
    print(f"\x1b[32mexit status: \x1b[39m{response.exit_status}")


class Input:
    def __init__(self):
        self.done = False

    def get_code(self) -> str:
        lines = []
        while True:
            line = input()
            if not line:
                break
            lines.append(line)
        return "\n".join(lines)


def unwrap_code_block(statement: str) -> Tuple[str, str, str]:
    """Removes triple backticks and a syntax name around a code block

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


def parse_exec_language(language: str, expression: str) -> Tuple[str, str]:
    """Changes some language names so TIO will understand, and wraps jargon for some languages"""
    if language in ("txt", "py", "python"):
        language = "python3"
    elif language in ("cpp", "c++"):
        language = "cpp-clang"
        if "int main(" not in expression:
            expression = wrap_with_cpp_jargon(expression)
    elif language == "c":
        language = "c-clang"
        if "int main(" not in expression:
            expression = wrap_with_c_jargon(expression)
    elif language == "java":
        language = "java-openjdk"
        if "public static void main(String[] args)" not in expression:
            expression = wrap_with_java_jargon(expression)
    elif language in ("cs", "c#"):
        language = "cs-csc"
        if "static void Main(string[] args)" not in expression:
            expression = wrap_with_cs_jargon(expression)
    elif language in ("js", "javascript"):
        language = "javascript-node"
    elif language == "swift":
        language = "swift4"

    return language, expression


def wrap_with_cpp_jargon(expression: str) -> str:
    """Wraps C++ code with common C++ jargon"""
    return get_cpp_jargon_header() + expression + "}"


def wrap_with_c_jargon(expression: str) -> str:
    """Wraps C code with common C jargon"""
    return get_c_jargon_header() + expression + "}"


def wrap_with_java_jargon(expression: str) -> str:
    """Wraps Java code with common Java jargon"""
    return get_java_jargon_header() + expression + "}}"


def wrap_with_cs_jargon(expression: str) -> str:
    """Wraps C# code with common C# jargon"""
    return get_cs_jargon_header() + expression + "}}}"


def get_cpp_jargon_header() -> str:
    """Returns the starting jargon for C++ (not including closing brackets)"""
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


def get_c_jargon_header() -> str:
    """Returns the starting jargon for C (not including closing brackets)"""
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


def get_java_jargon_header() -> str:
    """Returns the starting jargon for Java (not including closing brackets)"""
    return dedent(
        """
        import java.util.*;

        class MyClass {
            public static void main(String[] args) {
                Scanner scanner = new Scanner(System.in);
        """
    )


def get_cs_jargon_header() -> str:
    """Returns the starting jargon for C# (not including closing brackets)"""
    return dedent(
        """
        namespace MyNamespace {
            class MyClass {         
                static void Main(string[] args) {
        """
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt")
    except ValueError as e:
        print(e)
