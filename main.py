from aliases import dealias
from aliases import delete_alias
from aliases import load_aliases
from errors import InputError
from jargon import init_jargon
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
import keyboard  # https://pypi.org/project/keyboard/
import platform
import sqlite3


VERSION = "0.3.0"


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
        database_file_name = "run-quick database.db"
        aliases: Dict[str, str] = await load_aliases(database_file_name)
        languages: List[str] = await load_languages(
            loop, session, database_file_name, aliases
        )
        await init_jargon(database_file_name)
        chosen_lang = input("\x1b[32mlanguage: \x1b[39m").lower().strip()
        if chosen_lang == "help":
            await print_help()
        elif chosen_lang.startswith("jargon "):
            chosen_lang = chosen_lang.replace("jargon ", "").strip()
            if chosen_lang not in languages:
                print(f"Invalid language: `{chosen_lang}`")
            await print_jargon(chosen_lang, database_file_name)
        elif chosen_lang == "list" or chosen_lang.startswith("list "):
            filter_prefix = ""
            if chosen_lang.startswith("list "):
                filter_prefix = chosen_lang.replace("list ", "").strip()
            await list_languages(languages, aliases, filter_prefix)
        elif chosen_lang.startswith("alias "):
            chosen_lang = chosen_lang.replace("alias ", "").strip()
            if chosen_lang not in languages:
                print(f"Invalid language: `{chosen_lang}`")
            if chosen_lang in aliases:
                print(f"`{chosen_lang}` is an alias of `{aliases[chosen_lang]}`")
            else:
                print(f"`{chosen_lang}` is not an alias")
        elif chosen_lang.startswith("delete alias "):
            chosen_lang = chosen_lang.replace("delete alias ", "").strip()
            if chosen_lang not in languages:
                print(f"Invalid language: `{chosen_lang}`")
            if chosen_lang in aliases:
                await delete_alias(chosen_lang, aliases, languages, database_file_name)
                print(f"Deleted alias `{chosen_lang}`")
            else:
                print(f"`{chosen_lang}` is not an alias")
        else:
            if chosen_lang not in languages:
                print(f"Invalid language: `{chosen_lang}`")
            chosen_lang, code, inputs = await get_code(
                chosen_lang, aliases, database_file_name
            )
            await run_code(
                loop,
                session,
                database_file_name,
                languages,
                aliases,
                chosen_lang,
                code,
                inputs,
            )


async def load_languages(
    loop, session, database_file_name: str, aliases: Dict[str, str]
) -> List[str]:
    """Loads all languages from the database.

    Creates the database with default languages if it doesn't exist. The
    languages include the aliases.
    """
    try:
        with sqlite3.connect(database_file_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT language_name FROM languages")
            languages: List[Tuple[str]] = cursor.fetchall()
            return [e[0] for e in languages]
    except sqlite3.OperationalError:
        return await create_languages_table(loop, session, database_file_name, aliases)


async def save_languages(database_file_name: str, languages: List[str]) -> None:
    with sqlite3.connect(database_file_name) as conn:
        cursor = conn.cursor()
        await _save_languages(cursor, languages)
        conn.commit()


async def _save_languages(cursor, languages: List[str]) -> None:
    languages = [[e] for e in languages]
    cursor.executemany(
        """
        INSERT OR IGNORE INTO languages
        (language_name)
        VALUES (?);
        """,
        languages,
    )


async def create_languages_table(
    loop, session, database_file_name: str, aliases: Dict[str, str]
) -> List[str]:
    """Creates a database table for and returns all languages.

    Assumes the table does not exist.
    """
    async with await async_tio.Tio(loop=loop, session=session) as tio:
        languages = tio.languages
        languages.extend(aliases.keys())
    with sqlite3.connect(database_file_name) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE languages (
                id INTEGER PRIMARY KEY,
                language_name TEXT NOT NULL,
                UNIQUE (language_name)
            );
            """
        )
        await _save_languages(cursor, languages)
        conn.commit()
    return languages


async def print_help() -> None:
    print(
        dedent(
            """\
            help
                Displays this message.
            \x1b[90;3m(language)\x1b[0m
                Selects a language and then asks you for code to run.
            jargon \x1b[90;3m(language)\x1b[0m
                Shows the code that can wrap around your code in a chosen language.
            list
                Shows all supported languages and all of their aliases.
            list \x1b[90;3m(prefix)\x1b[0m
                Shows all supported languages and aliases that start with a chosen
                prefix.
            alias \x1b[90;3m(alias)\x1b[0m
                Shows the base language of an alias.
            delete alias \x1b[90;3m(alias)\x1b[0m
                Deletes an alias and any jargon it has.
            
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
    database_file_name: str,
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
            await save_languages(database_file_name, languages)
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
