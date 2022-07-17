from aliases import create_alias
from aliases import delete_alias
from aliases import load_aliases
from errors import InputError
from jargon import create_jargon
from jargon import delete_jargon
from jargon import has_jargon
from jargon import init_jargon
from jargon import print_jargon
from jargon import wrap_jargon
from multiline_input import get_lines
from textwrap import dedent
from typing import Dict
from typing import List
from typing import Tuple
import aiohttp  # https://docs.aiohttp.org/en/stable/
import argparse
import async_tio  # https://pypi.org/project/async-tio/
import asyncio
import sqlite3
import sys


VERSION = "0.3.0"


def init_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        usage="%(prog)s [OPTION]",
        description="Quickly run code in almost any language.",
        epilog="For tips, the source code, discussions, and more, visit https://github.com/wheelercj/run-quick",
    )
    parser.add_argument("-v", "--version", action="version", version=f"v{VERSION}")
    return parser


def main() -> None:
    _ = init_argparse().parse_args()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(amain(loop))


async def amain(loop) -> None:
    async with aiohttp.ClientSession(loop=loop) as session:
        db_file_name = "run-quick database.db"
        aliases: Dict[str, str] = await load_aliases(db_file_name)
        languages: List[str] = await load_languages(
            loop, session, db_file_name, aliases
        )
        await init_jargon(db_file_name)
        while True:
            try:
                choice = input("\x1b[32mrq> \x1b[39m").lower().strip()
                await parse_choice(
                    loop, session, db_file_name, languages, aliases, choice
                )
            except InputError as e:
                print(e)


async def parse_choice(
    loop,
    session,
    db_file_name: str,
    languages: List[str],
    aliases: Dict[str, str],
    choice: str,
) -> None:
    if choice == "help":
        await print_help()
    elif choice == "exit":
        sys.exit(0)
    elif choice.startswith("run "):
        language = choice.replace("run ", "").strip()
        if language not in languages:
            raise InputError(f"Invalid language: `{language}`")
        language, code, inputs = await get_code(language, aliases, db_file_name)
        await run_code(
            loop,
            session,
            db_file_name,
            languages,
            aliases,
            language,
            code,
            inputs,
        )
    elif choice == "list" or choice.startswith("list "):
        filter_prefix = ""
        if choice.startswith("list "):
            filter_prefix = choice.replace("list ", "").strip()
        await list_languages(languages, aliases, filter_prefix)
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
                raise InputError("Cancelled creating new jargon.")
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
                'Error: expected two words after "create alias": '
                "the new alias and the language being aliased"
            )
        new_alias, language = split_choice
        if new_alias in aliases:
            raise InputError(f"`{new_alias}` is already an alias.")
        if new_alias in languages:
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


async def load_languages(
    loop, session, db_file_name: str, aliases: Dict[str, str]
) -> List[str]:
    """Loads all languages from the database.

    Creates the database with default languages if it doesn't exist. The
    languages include the aliases.
    """
    try:
        with sqlite3.connect(db_file_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT language FROM languages")
            languages: List[Tuple[str]] = cursor.fetchall()
            return [e[0] for e in languages]
    except sqlite3.OperationalError:
        return await create_languages_table(loop, session, db_file_name, aliases)


async def save_languages(db_file_name: str, languages: List[str]) -> None:
    with sqlite3.connect(db_file_name) as conn:
        cursor = conn.cursor()
        await _save_languages(cursor, languages)
        conn.commit()


async def _save_languages(cursor, languages: List[str]) -> None:
    languages = [[e] for e in languages]
    cursor.executemany(
        """
        INSERT OR IGNORE INTO languages
        (language)
        VALUES (?);
        """,
        languages,
    )


async def create_languages_table(
    loop, session, db_file_name: str, aliases: Dict[str, str]
) -> List[str]:
    """Creates a database table for and returns all languages.

    Assumes the table does not exist.
    """
    async with await async_tio.Tio(loop=loop, session=session) as tio:
        languages = tio.languages
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
            list \x1b[90;3m(prefix)\x1b[0m
                Shows all supported languages that start with a chosen prefix.
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
    loop,
    session,
    db_file_name: str,
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
            await save_languages(db_file_name, languages)
        response = await tio.execute(code, language=chosen_language, inputs=inputs)
    print(end=f"\x1b[32m`{chosen_language}` output:\x1b[39m\n{response.stdout}")
    if not response.stdout.endswith("\n"):
        print()
    print(f"\x1b[32mexit status: \x1b[39m{response.exit_status}")


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
