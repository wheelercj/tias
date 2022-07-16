from aliases import dealias
from aliases import load_aliases
from jargon import print_jargon
from jargon import wrap_jargon
from textwrap import dedent
from typing import Dict
from typing import List
from typing import Tuple
import aiohttp  # https://docs.aiohttp.org/en/stable/
import argparse
import async_tio  # https://pypi.org/project/async-tio/
import asyncio
import json
import keyboard  # https://pypi.org/project/keyboard/
import platform


VERSION = "0.3.0"


class InputError(Exception):
    pass


def init_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        usage="%(prog)s [OPTION]",
        description="Quickly run code in almost any language. When prompted "
        "for a language, enter \x1b[100mhelp\x1b[0m for more options.",
    )
    parser.add_argument("-v", "--version", action="version", version=f"v{VERSION}")
    return parser


def main() -> None:
    _ = init_argparse().parse_args()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(amain(loop))


async def amain(loop) -> None:
    async with aiohttp.ClientSession(loop=loop) as session:
        languages_file_name = "valid_languages.json"
        database_file_name = "database.db"
        languages, aliases = await get_languages(
            loop, session, languages_file_name, database_file_name
        )
        chosen_language = input("\x1b[32mlanguage: \x1b[39m").lower().strip()
        if chosen_language == "help":
            await print_help()
        elif chosen_language.endswith(" jargon"):
            chosen_language = chosen_language[: -len(" jargon")].strip()
            if chosen_language not in languages:
                raise InputError(f"Invalid language: `{chosen_language}`")
            await print_jargon(chosen_language, database_file_name)
        elif chosen_language.startswith("list"):
            filter_prefix = ""
            if len(chosen_language) > len("list"):
                filter_prefix = chosen_language[len("list") :].strip()
            await list_languages(languages, aliases, filter_prefix)
        else:
            if chosen_language not in languages:
                raise InputError(f"Invalid language: `{chosen_language}`")
            chosen_language, code, inputs = await get_code(
                chosen_language, aliases, database_file_name
            )
            await run_code(
                loop,
                session,
                languages_file_name,
                languages,
                aliases,
                chosen_language,
                code,
                inputs,
            )


async def get_languages(
    loop, session, languages_file_name: str, database_file_name: str
) -> Tuple[List[str], Dict[str, str]]:
    aliases: Dict[str, str] = await load_aliases(database_file_name)
    try:
        with open(languages_file_name, "r", encoding="utf8") as file:
            languages = json.load(file)
            for alias in aliases.keys():
                if alias not in languages:
                    languages.append(alias)
    except FileNotFoundError:
        async with await async_tio.Tio(loop=loop, session=session) as tio:
            languages = tio.languages
            languages.extend(aliases.keys())
            await save_languages(languages_file_name, languages)
    return languages, aliases


async def save_languages(languages_file_name: str, languages: List[str]) -> None:
    with open(languages_file_name, "w", encoding="utf8") as file:
        json.dump(languages, file)


async def print_help() -> None:
    print(
        dedent(
            """\
            help
                Displays this message.
            \x1b[90;3m(language)\x1b[0m
                Selects a language and then asks you for code to run.
            \x1b[90;3m(language)\x1b[0m jargon
                Shows the code that can wrap around your code in a chosen language.
            list
                Shows all supported languages and all of their aliases.
            list \x1b[90;3m(prefix)\x1b[0m
                Shows all supported languages and aliases that start with a chosen
                prefix.
            
            For more help, visit https://github.com/wheelercj/run-quick
            """
        )
    )


async def list_languages(
    valid_languages: List[str], aliases: Dict[str, str], filter_prefix: str
) -> None:
    """Lists supported languages, optionally filtered by a prefix."""
    if filter_prefix:
        valid_languages = list(
            filter(lambda s: s.startswith(filter_prefix), valid_languages)
        )
        lang_count = len(valid_languages)
        print(end=f"languages that start with `{filter_prefix}` ({lang_count}): ")
    else:
        print(end=f"languages ({len(valid_languages) - len(aliases)}): ")
    valid_languages = sorted(valid_languages)
    alias_included = False
    for i, language in enumerate(valid_languages):
        if language in aliases:
            alias_included = True
            valid_languages[i] = f"\x1b[36m{language}\x1b[0m"
    valid_languages = ", ".join(valid_languages)
    print(valid_languages)
    if alias_included:
        print("\x1b[90m(Aliases are shown in blue).\x1b[0m")


async def get_code(
    chosen_language: str, aliases: Dict[str, str], database_file_name: str
) -> Tuple[str, str, str]:
    print(end="\x1b[32mcode: \x1b[90m(")
    if platform == "darwin":
        print(end="cmd")
    else:
        print(end="ctrl")
    print("+enter to run)\x1b[39m")
    code: str = Input().get_code()
    inputs = ""
    if "```" in code:
        code, inputs = await unwrap_code_block(code)
    code = await wrap_jargon(code, chosen_language, database_file_name)
    chosen_language = await dealias(chosen_language, aliases)
    return chosen_language, code, inputs


async def run_code(
    loop,
    session,
    languages_file_name: str,
    languages: List[str],
    aliases: Dict[str, str],
    chosen_language: str,
    code: str,
    inputs: str,
) -> None:
    async with await async_tio.Tio(loop=loop, session=session) as tio:
        if len(languages) - len(aliases) != len(tio.languages):
            languages = tio.languages
            languages.extend(aliases.keys())
            await save_languages(languages_file_name, languages)
        response = await tio.execute(code, language=chosen_language, inputs=inputs)
    print(end=f"\x1b[32m`{chosen_language}` output:\x1b[39m\n{response.stdout}")
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
        keyboard.write("\n")  # Some terminals require this for `input` to return.
        self.receiving_input = not self.receiving_input


async def unwrap_code_block(statement: str) -> Tuple[str, str]:
    """Removes triple backticks around a code block.

    Returns the input unchanged and an empty string if there are no triple
    backticks. Anything after closing triple backticks is returned as the
    second string. Closing triple backticks are otherwise optional.
    """
    if not statement.startswith("```"):
        return statement, ""
    statement = statement[3:]
    if statement.startswith("\n"):
        statement = statement[1:]
    suffix = ""
    if "```" in statement:
        statement, suffix = statement.split("```", 1)
    if statement.endswith("\n"):
        statement = statement[:-1]
    return statement, suffix


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt")
    except InputError as e:
        print(e)
