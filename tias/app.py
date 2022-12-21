import argparse
import asyncio
import sqlite3
import sys
from contextlib import contextmanager
from textwrap import dedent
from typing import Dict
from typing import List
from typing import Tuple

import aiohttp  # https://docs.aiohttp.org/en/stable/
import async_tio  # https://pypi.org/project/async-tio/

from tias.aliases import create_alias
from tias.aliases import delete_alias
from tias.aliases import load_aliases
from tias.errors import InputError
from tias.jargon import create_jargon
from tias.jargon import delete_jargon
from tias.jargon import has_jargon
from tias.jargon import init_jargon
from tias.jargon import print_jargon
from tias.jargon import wrap_jargon
from tias.multiline_input import get_lines


VERSION = "0.5.1"


def init_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        usage="%(prog)s [OPTION]",
        description="Quickly run code in almost any language.",
        epilog="For tips, the source code, discussions, and more, visit"
        " https://github.com/wheelercj/tias",
    )
    parser.add_argument("-v", "--version", action="version", version=f"v{VERSION}")
    return parser


def main() -> None:
    _ = init_argparse().parse_args()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(amain())


async def amain() -> None:
    connector = aiohttp.TCPConnector(force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        with suppress_stderr():
            async with async_tio.Tio(session=session) as tio:
                db_file_name = "tias.db"
                aliases: Dict[str, str] = await load_aliases(db_file_name)
                languages: List[str] = await load_languages(tio, db_file_name, aliases)
                await init_jargon(db_file_name)
                while True:
                    try:
                        choice = input("\x1b[32mtias> \x1b[39m").lower().strip()
                        await parse_choice(
                            tio, db_file_name, languages, aliases, choice
                        )
                    except InputError as e:
                        print(e)


@contextmanager
def suppress_stderr():
    "Suppresses writes to stderr"

    class Null:
        write = lambda *args: None  # noqa: E731

    err, sys.stderr = sys.stderr, Null
    try:
        yield
    finally:
        sys.stderr = err


async def parse_choice(
    tio,
    db_file_name: str,
    languages: List[str],
    aliases: Dict[str, str],
    choice: str,
) -> None:
    if choice == "help":
        await print_help()
    elif choice == "exit":
        sys.exit(0)
    elif choice == "":
        return
    elif choice.startswith("run "):
        language = choice.replace("run ", "").strip()
        if language not in languages:
            raise InputError(f"Invalid language: `{language}`")
        language, code, inputs = await get_code(language, aliases, db_file_name)
        if not code:
            raise InputError("Error: no code was given to run.")
        await run_code(
            tio,
            db_file_name,
            languages,
            aliases,
            language,
            code,
            inputs,
        )
    elif choice == "list" or choice.startswith("list "):
        filter_keyword = ""
        if choice.startswith("list "):
            filter_keyword = choice.replace("list ", "").strip()
        await list_languages(languages, aliases, filter_keyword)
    elif choice == "ls" or choice.startswith("ls "):
        filter_keyword = ""
        if choice.startswith("ls "):
            filter_keyword = choice.replace("ls ", "").strip()
        await list_languages(languages, aliases, filter_keyword)
    elif choice.startswith("jargon "):
        language = choice.replace("jargon ", "").strip()
        if language not in languages:
            raise InputError(f"Invalid language: `{language}`")
        await print_jargon(language, db_file_name)
    elif choice.startswith("create jargon "):
        language = choice.replace("create jargon ", "").strip()
        if language not in languages:
            raise InputError(f"Invalid language: `{language}`")
        if await has_jargon(language, db_file_name):
            c = input(f"`{language}` already has jargon. Overwrite? (y/n) ")
            if c.lower().strip() not in ("y", "yes"):
                raise InputError("Cancelled creating jargon.")
            await delete_jargon(language, db_file_name)
        await create_jargon(language, db_file_name)
        print(f"Created jargon for the `{language}` language")
    elif choice.startswith("delete jargon "):
        language = choice.replace("delete jargon ", "").strip()
        if language not in languages:
            raise InputError(f"Invalid language: `{language}`")
        if not await has_jargon(language, db_file_name):
            raise InputError(f"`{language}` has no jargon")
        await delete_jargon(language, db_file_name)
        print(f"Jargon for the `{language}` language deleted.")
    elif choice.startswith("alias "):
        alias = choice.replace("alias ", "").strip()
        if alias not in languages:
            raise InputError(f"Invalid language: `{alias}`")
        if alias not in aliases:
            raise InputError(f"`{alias}` is not an alias")
        print(f"`{alias}` is an alias of `{aliases[alias]}`")
    elif choice.startswith("create alias "):
        choice = choice.replace("create alias ", "").strip()
        split_choice = choice.split()
        if len(split_choice) != 2:
            raise InputError(
                'Error: expected two words after "create alias":\n'
                "the new alias and the language being aliased."
            )
        new_alias, language = split_choice
        if new_alias in aliases:
            if language == aliases[new_alias]:
                raise InputError(f"`{new_alias}` is already an alias of `{language}`.")
            c = input(f"`{new_alias}` is already an alias. Overwrite? (y/n) ")
            if c.lower().split() not in ("y", "yes"):
                raise InputError("Cancelled creating an alias.")
        elif new_alias in languages:
            raise InputError(f"`{new_alias}` is already a language.")
        if language not in languages:
            raise InputError(f"Invalid language: `{language}`")
        if language in aliases:
            language = aliases[language]
        await create_alias(db_file_name, new_alias, language, aliases, languages)
        print(f"Created `{new_alias}` as an alias to `{language}`")
    elif choice.startswith("delete alias "):
        alias = choice.replace("delete alias ", "").strip()
        if alias not in aliases:
            raise InputError(f"`{alias}` is not an alias")
        await delete_alias(alias, aliases, languages, db_file_name)
        print(f"Deleted alias `{alias}`")
    else:
        raise InputError("Invalid input. Enter \x1b[100mhelp\x1b[0m for help.")


async def load_languages(tio, db_file_name: str, aliases: Dict[str, str]) -> List[str]:
    """Loads all languages from the database.

    Creates the database with default languages if it doesn't exist. The languages
    include the aliases.
    """
    try:
        with sqlite3.connect(db_file_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT language FROM languages")
            languages: List[Tuple[str]] = cursor.fetchall()
            return [e[0] for e in languages]
    except sqlite3.OperationalError:
        return await create_languages_table(tio, db_file_name, aliases)


async def save_languages(db_file_name: str, languages: List[str]) -> None:
    with sqlite3.connect(db_file_name) as conn:
        cursor = conn.cursor()
        await _save_languages(cursor, languages)
        conn.commit()


async def _save_languages(cursor, languages: List[str]) -> None:
    language_lists = [[e] for e in languages]
    cursor.executemany(
        """
        INSERT OR IGNORE INTO languages
        (language)
        VALUES (?);
        """,
        language_lists,
    )


async def create_languages_table(
    tio, db_file_name: str, aliases: Dict[str, str]
) -> List[str]:
    """Creates a database table for and returns all languages.

    Assumes the table does not exist.
    """
    languages: List[str] = [x.tio_name for x in await tio.get_languages()]
    languages.extend(aliases.keys())
    with sqlite3.connect(db_file_name) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE languages (
                id INTEGER PRIMARY KEY,
                language TEXT NOT NULL,
                UNIQUE (language)
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
            exit
                Closes this app.
            run \x1b[90;3m(language)\x1b[0m
                Selects a language and then asks you for code to run.
            list
                Shows all supported languages.
            list \x1b[90;3m(search term)\x1b[0m
                Shows all supported languages that contain a chosen search term.
            jargon \x1b[90;3m(language)\x1b[0m
                Shows the code that can wrap around your code in a chosen language.
            create jargon \x1b[90;3m(language)\x1b[0m
                Allows you to set the jargon for a language.
            delete jargon \x1b[90;3m(language)\x1b[0m
                Deletes the jargon for a language.
            alias \x1b[90;3m(alias)\x1b[0m
                Shows the language an alias is an alias of.
            create alias \x1b[90;3m(new alias)\x1b[0m \x1b[90;3m(language)\x1b[0m
                Creates a new alias for a chosen language.
            delete alias \x1b[90;3m(alias)\x1b[0m
                Deletes an alias and any jargon it has.
            For more help, visit https://github.com/wheelercj/tias\
            """
        )
    )


async def list_languages(
    valid_languages: List[str], aliases: Dict[str, str], filter_keyword: str
) -> None:
    """Lists supported languages, optionally filtered with a search term."""
    if filter_keyword:
        valid_languages = list(filter(lambda s: filter_keyword in s, valid_languages))
        lang_count = len(valid_languages)
        print(end=f"languages that contain `{filter_keyword}` ({lang_count}): ")
    else:
        print(end=f"languages ({len(valid_languages) - len(aliases)}): ")
    valid_languages = sorted(valid_languages)
    alias_included = False
    for i, language in enumerate(valid_languages):
        if language in aliases:
            alias_included = True
            valid_languages[i] = f"\x1b[36m{language}\x1b[0m"
    valid_languages_s = ", ".join(valid_languages)
    print(valid_languages_s)
    if alias_included:
        print("\x1b[90m(Aliases are shown in blue).\x1b[0m")


async def get_code(
    chosen_language: str, aliases: Dict[str, str], db_file_name: str
) -> Tuple[str, str, str]:
    print(end="\x1b[32mcode: \x1b[0m")
    code = get_lines()
    inputs = ""
    if "```" in code:
        code, inputs = await unwrap_code_block(code)
    code = await wrap_jargon(code, chosen_language, db_file_name)
    if chosen_language in aliases:
        chosen_language = aliases[chosen_language]
    return chosen_language, code, inputs


async def run_code(
    tio,
    db_file_name: str,
    languages: List[str],
    aliases: Dict[str, str],
    chosen_language: str,
    code: str,
    inputs: str,
) -> None:
    temp_languages: List[str] = [x.tio_name for x in await tio.get_languages()]
    if len(languages) - len(aliases) != len(temp_languages):
        languages = temp_languages
        languages.extend(aliases.keys())
        await save_languages(db_file_name, languages)
    print("\x1b[90mRunning...\x1b[0m")
    response = await tio.execute(code, language=chosen_language, inputs=inputs)
    print(end=f"\x1b[32m`{chosen_language}` output:\x1b[39m\n{response.stdout}")
    if not response.stdout.endswith("\n"):
        print()
    print(f"\x1b[32mexit status: \x1b[39m{response.exit_status}")


async def unwrap_code_block(statement: str) -> Tuple[str, str]:
    """Removes triple backticks around a code block.

    Returns the input unchanged and an empty string if there are no triple backticks.
    Anything after closing triple backticks is returned as the second string. Closing
    triple backticks are otherwise optional.
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
