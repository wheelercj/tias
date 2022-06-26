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
    language = input("language: ")
    print('code:')
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

    # @commands.group(
    #     name="run", aliases=["exec", "execute"], invoke_without_command=True
    # )
    # async def _run(self, ctx, *, code_block: str):
    #     """A group of commands for executing code in almost any language

    #     Without a subcommand, this command executes code in almost any language.
    #     You can use a markdown-style code block and specify a language.
    #     """
    #     async with ctx.typing():
    #         language, expression, inputs = await unwrap_code_block(code_block)
    #         language, expression = await self.parse_exec_language(language, expression)

    #         async with await async_tio.Tio(
    #             loop=self.bot.loop, session=self.bot.session
    #         ) as tio:
    #             if language not in tio.languages:
    #                 raise commands.BadArgument(f"Invalid language: {language}")

    #             result = await tio.execute(expression, language=language, inputs=inputs)
    #         await ctx.send(f"`{language}` output:\n" + str(result))

    # @_run.command(name="guide", aliases=["g", "i", "h", "info", "help"])
    # async def exec_guide(self, ctx):
    #     """Explains some of the nuances of the `run` command"""
    #     await ctx.send(
    #         " ".join(
    #             dedent(
    #                 """
    #         With the `run` command, you can use a triple-backtick code block
    #         and specify a language on its first line. Any input after the
    #         closing triple backticks will be used as inputs for the program
    #         (you can hold shift while pressing enter to go to the next line if
    #         necessary). If you choose c, c++, cpp, java, c#, or cs as the
    #         language and you only need the main function, you may not need to
    #         type the function header and commonly needed code above main. You
    #         can use the `run jargon <language>` command to see what code may be
    #         automatically added in front of your input if you omit the function
    #         header.

    #         Some language names will be changed before the code is executed:
    #         c -> c-clang
    #         c++ or cpp -> cpp-clang
    #         c# or cs -> cs-csc
    #         java -> java-openjdk
    #         py or python -> python3
    #         js or javascript -> javascript-node
    #         swift -> swift4

    #         After this processing, the `run` command sends your code to
    #         https://tio.run and receives any outputs specified in your code
    #         (as well as info about how long it took to run).
    #         """
    #             ).split("\n")
    #         )
    #     )

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

    # @_run.command(name="jargon", aliases=["j"])
    # async def send_jargon(self, ctx, language: str):
    #     """Shows the jargon the `run` command uses for a language (currently only c, c++, cpp, java, c#, or cs)"""
    #     if language in ("c++", "cpp"):
    #         jargon = await self.get_cpp_jargon_header()
    #         await ctx.send(jargon)
    #     elif language == "c":
    #         jargon = await self.get_c_jargon_header()
    #         await ctx.send(jargon)
    #     elif language == "java":
    #         jargon = await self.get_java_jargon_header()
    #         await ctx.send(jargon)
    #     elif language in ("c#", "cs"):
    #         jargon = await self.get_cs_jargon_header()
    #         await ctx.send(jargon)
    #     else:
    #         raise commands.BadArgument(
    #             f"No jargon wrapping has been set for the {language} language"
    #         )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt")
    except ValueError as e:
        print(e)
