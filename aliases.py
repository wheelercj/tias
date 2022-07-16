from typing import Dict
import sqlite3


async def dealias(language: str, aliases: Dict[str, str]) -> str:
    """Changes aliases to default languages, returns default languages unchanged."""
    if language in aliases:
        return aliases[language]
    return language


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
                language_name TEXT NOT NULL);
            """
        )
        for alias_name, language_name in default_aliases.items():
            cursor.execute(
                """
                INSERT INTO aliases
                (alias_name, language_name)
                VALUES (?, ?);
                """,
                (alias_name, language_name),
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
