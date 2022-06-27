import aiohttp  # https://docs.aiohttp.org/en/stable/
import async_tio  # https://pypi.org/project/async-tio/
import asyncio
import keyboard  # https://pypi.org/project/keyboard/
from textwrap import dedent
from typing import Tuple


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(amain(loop))


async def amain(loop):
    language = input("language: ").lower().strip()
    if language.endswith(" jargon"):
        language = language[: -len(" jargon")].strip()
        await print_jargon(language)
    else:
        await get_and_run_code(loop, language)


async def print_jargon(language: str):
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


async def get_and_run_code(loop, language: str):
    print("code:")
    code: str = Input().get_code()
    inputs = ""
    if "```" in code:
        _, code, inputs = unwrap_code_block(code)
    language, code = parse_exec_language(language, code)
    async with aiohttp.ClientSession(loop=loop) as session:
        async with await async_tio.Tio(loop=loop, session=session) as tio:
            if language not in tio.languages:
                raise ValueError(f"Invalid language: `{language}`")
            result = await tio.execute(code, language=language, inputs=inputs)
    print(f"`{language}` output:\n{result}")


class Input:
    def __init__(self):
        self.done = False

    def get_code(self) -> str:
        keyboard.add_hotkey("ctrl+enter", self._toggle_done)
        lines = []
        empty_count = 0
        while not self.done:
            line = input()
            if not line:
                empty_count += 1
            else:
                empty_count = 0
            if empty_count == 3:
                break
            lines.append(line)
        return "\n".join(lines)

    def _toggle_done(self):
        self.done = not self.done


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

    # @_run.command(name="languages", aliases=["l", "s", "langs", "list", "search"])
    # async def list_programming_languages(self, ctx, *, query: str = None):
    #     """Lists the languages supported by the `run` command that contain an optional search word

    #     e.g. `run languages py` will only show languages that contain `py`.
    #     You can also see a full list of supported languages here: https://tio.run/#
    #     """
    #     if query is None:
    #         await ctx.send(
    #             "You can optionally choose a search term, e.g. "
    #             '`run languages py` will only show languages that contain "py"'
    #         )
    #         title = "languages supported by the `run` command"
    #     else:
    #         title = f"supported languages that contain `{query}`"
    #     async with await async_tio.Tio(
    #         loop=self.bot.loop, session=self.bot.session
    #     ) as tio:
    #         valid_languages = tio.languages
    #         valid_languages.extend(
    #             [
    #                 "c",
    #                 "c#",
    #                 "c++",
    #                 "cpp",
    #                 "cs",
    #                 "java",
    #                 "javascript",
    #                 "js",
    #                 "py",
    #                 "python",
    #                 "swift",
    #             ]
    #         )
    #         valid_languages = sorted(valid_languages, key=len)
    #         await paginate_search(ctx, title, valid_languages, query)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt")
    except ValueError as e:
        print(e)
