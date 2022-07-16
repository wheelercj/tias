from typing import Dict
from typing import List
import sqlite3


async def create_aliases_table(database_file_name: str) -> Dict[str, str]:
    """Creates a sqlite table with default aliases and returns all aliases.

    Assumes the table does not exist.
    """
    default_aliases = {
        "c": "c-clang",
        "c#": "cs-csc",
        "c++": "cpp-clang",
        "cpp": "cpp-clang",
        "cs": "cs-csc",
        "f#": "fs-core",
        "fs": "fs-core",
        "java": "java-openjdk",
        "javascript": "javascript-node",
        "js": "javascript-node",
        "objective-c": "objective-c-clang",
        "py": "python3",
        "python": "python3",
        "swift": "swift4",
    }
    with sqlite3.connect(database_file_name) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE aliases (
                id INTEGER PRIMARY KEY,
                alias_name TEXT NOT NULL,
                language_name TEXT NOT NULL,
                UNIQUE (alias_name)
            );
            """
        )
        cursor.executemany(
            """
            INSERT OR IGNORE INTO aliases
            (alias_name, language_name)
            VALUES (?, ?);
            """,
            default_aliases.items(),
        )
        conn.commit()
    return default_aliases


async def load_aliases(database_file_name: str) -> Dict[str, str]:
    """Loads aliases from the database.

    Returns an empty dictionary if there are no aliases.
    """
    try:
        with sqlite3.connect(database_file_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT alias_name, language_name FROM aliases")
            records = cursor.fetchall()
            if not records:
                return dict()
            all_aliases = dict()
            for alias_name, language_name in records:
                all_aliases[alias_name] = language_name
            return all_aliases
    except sqlite3.OperationalError:
        return await create_aliases_table(database_file_name)


async def create_alias(
    database_file_name: str,
    new_alias: str,
    language: str,
    aliases: Dict[str, str],
    languages: List[str],
) -> None:
    aliases[new_alias] = language
    languages.append(new_alias)
    with sqlite3.connect(database_file_name) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO languages
            (language_name)
            VALUES (?);
            """,
            [new_alias]
        )
        cursor.execute(
            """
            INSERT INTO aliases
            (alias_name, language_name)
            VALUES (?, ?);
            """,
            (new_alias, language)
        )


async def delete_alias(
    alias: str, aliases: Dict[str, str], languages: List[str], database_file_name: str
):
    del aliases[alias]
    languages.remove(alias)
    with sqlite3.connect(database_file_name) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM aliases
            WHERE alias_name = ?;
            """,
            [alias],
        )
        cursor.execute(
            """
            DELETE FROM languages
            WHERE language_name = ?;
            """,
            [alias],
        )
        cursor.execute(
            """
            DELETE FROM jargon
            WHERE alias_or_language_name = ?;
            """,
            [alias],
        )
