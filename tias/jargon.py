import sqlite3
from textwrap import dedent
from typing import Dict
from typing import Tuple

from tias.errors import InputError
from tias.multiline_input import get_lines


async def init_jargon(db_file_name: str) -> None:
    """Creates a jargon table in the database if it doesn't exist."""
    with sqlite3.connect(db_file_name) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'jargon';
            """
        )
        if not cursor.fetchall():
            await create_jargon_table(db_file_name)


async def print_jargon(language: str, db_file_name: str) -> None:
    """Shows the jargon for a language if it has jargon."""
    jargon, jargon_key = await load_jargon(language, db_file_name)
    if jargon:
        print(f"\x1b[32mjargon:\x1b[0m\n{jargon}")
        print(f"\x1b[32mjargon key:\x1b[0m {jargon_key}")
    else:
        raise InputError(
            f"No jargon wrapping has been set for the `{language}` language"
        )


async def create_jargon_table(db_file_name: str) -> None:
    """Creates a sqlite table with default jargon.

    Assumes the table does not exist.
    """
    default_jargon: Dict[str, Tuple[str, str]] = await get_default_jargon()
    with sqlite3.connect(db_file_name) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE jargon (
                id INTEGER PRIMARY KEY,
                language TEXT NOT NULL,
                jargon_text TEXT NOT NULL,
                jargon_key TEXT NOT NULL,
                UNIQUE (language)
            );
            """
        )
        for language, (jargon, jargon_key) in default_jargon.items():
            await save_jargon(language, jargon, jargon_key, cursor)
        conn.commit()


async def save_jargon(language: str, jargon: str, jargon_key: str, cursor) -> None:
    """Saves to the database the jargon for a language."""
    cursor.execute(
        """
        INSERT OR IGNORE INTO jargon
        (language, jargon_text, jargon_key)
        VALUES (?, ?, ?);
        """,
        (language, jargon, jargon_key),
    )


async def load_jargon(language: str, db_file_name: str) -> Tuple[str, str]:
    """Gets jargon for a language from the database.

    Returns empty strings if the language has no jargon.

    Returns
    -------
    str
        The language's jargon.
    str
        The language's "jargon key", i.e. something in an expression that, if
        present, means jargon wrapping is not needed.
    """
    with sqlite3.connect(db_file_name) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT jargon_text, jargon_key
            FROM jargon
            WHERE language = ?;
            """,
            [language],
        )
        records = cursor.fetchall()
        if not records:
            return ("", "")
        jargon, jargon_key = records[0]
        return jargon, jargon_key


async def wrap_jargon(expression: str, language: str, db_file_name: str) -> str:
    """Wraps code around a given expression if the language has needed jargon.

    Returns the expression unchanged if the language has no jargon or if the
    jargon doesn't appear to be needed.
    """
    jargon, jargon_key = await load_jargon(language, db_file_name)
    if not jargon:
        return expression
    if jargon_key not in expression:
        return jargon.replace("INSERT_HERE", expression)
    return expression


async def has_jargon(language: str, db_file_name: str) -> bool:
    with sqlite3.connect(db_file_name) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM jargon
            WHERE language = ?;
            """,
            [language],
        )
        records = cursor.fetchall()
        return bool(records)


async def create_jargon(language: str, db_file_name: str) -> None:
    """Gets input for and adds jargon to the database.

    Assumes the language does not already have jargon.
    """
    print("Enter \x1b[100mINSERT_HERE\x1b[0m where you want code to be inserted.")
    print(end="\x1b[32mjargon: \x1b[0m")
    jargon = get_lines()
    if "INSERT_HERE" not in jargon:
        raise InputError("Error: the jargon must contain \x1b[100mINSERT_HERE\x1b[0m")
    print("\x1b[32m---\x1b[0m")
    print("Enter the jargon's key, i.e. a piece of code that, if present")
    print("within code submitted to run, means jargon wrapping is not needed.")
    print(end="\x1b[32mjargon key: \x1b[0m")
    jargon_key = get_lines()
    print("\x1b[32m---\x1b[0m")
    if not jargon_key:
        raise InputError("The jargon key must not be empty")
    with sqlite3.connect(db_file_name) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO jargon
            (language, jargon_text, jargon_key)
            VALUES (?, ?, ?);
            """,
            (language, jargon, jargon_key),
        )


async def delete_jargon(language: str, db_file_name: str) -> None:
    with sqlite3.connect(db_file_name) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM jargon
            WHERE language = ?;
            """,
            [language],
        )


async def get_default_jargon() -> Dict[str, Tuple[str, str]]:
    default_jargon: Dict[str, Tuple[str, str]] = {
        # keys: the language
        # values:
        #   * the jargon
        #   * the "jargon key"
        "c": (
            dedent(
                """\
                #include <stdbool.h>
                #include <stdio.h>

                int main(void) {
                    INSERT_HERE
                }\
                """
            ),
            "int main(",
        ),
        "cpp": (
            dedent(
                """\
                #include <iostream>
                #include <stdio.h>
                using namespace std;

                int main() {
                    INSERT_HERE
                }\
                """,
            ),
            "int main(",
        ),
        "cs": (
            dedent(
                """\
                namespace MyNamespace {
                    class MyClass {
                        static void Main(string[] args) {
                            INSERT_HERE
                        }
                    }
                }\
                """
            ),
            "static void Main(",
        ),
        "dart": (
            dedent(
                """\
                void main() {
                    INSERT_HERE
                }\
                """
            ),
            "void main(",
        ),
        "go": (
            dedent(
                """\
                package main
                import "fmt"

                func main() {
                    INSERT_HERE
                }\
                """
            ),
            "func main(",
        ),
        "java": (
            dedent(
                """\
                import java.util.*;

                class MyClass {
                    public static void main(String[] args) {
                        Scanner scanner = new Scanner(System.in);
                        INSERT_HERE
                    }
                }\
                """
            ),
            "public static void main(",
        ),
        "kotlin": (
            dedent(
                """\
                fun main(args : Array<String>) {
                    INSERT_HERE
                }\
                """
            ),
            "fun main(",
        ),
        "objective-c": (
            dedent(
                """\
                #include <stdio.h>
                // Print with the `puts` function, not `NSLog`.

                int main() {
                    INSERT_HERE
                }\
                """
            ),
            "int main(",
        ),
        "rust": (
            dedent(
                """\
                fn main() {
                    INSERT_HERE
                }\
                """
            ),
            "fn main(",
        ),
        "scala": (
            dedent(
                """\
                object Main extends App {
                    INSERT_HERE
                }\
                """
            ),
            "object Main",
        ),
    }
    default_jargon["c-clang"] = default_jargon["c"]
    default_jargon["c-gcc"] = default_jargon["c"]
    default_jargon["c-tcc"] = default_jargon["c"]
    default_jargon["c#"] = default_jargon["cs"]
    default_jargon["c++"] = default_jargon["cpp"]
    default_jargon["cpp-clang"] = default_jargon["cpp"]
    default_jargon["cpp-gcc"] = default_jargon["cpp"]
    default_jargon["cs-core"] = default_jargon["cs"]
    default_jargon["cs-csc"] = default_jargon["cs"]
    default_jargon["cs-csi"] = default_jargon["cs"]
    default_jargon["cs-mono-shell"] = default_jargon["cs"]
    default_jargon["cs-mono"] = default_jargon["cs"]
    default_jargon["java-jdk"] = default_jargon["java"]
    default_jargon["java-openjdk"] = default_jargon["java"]
    default_jargon["objective-c-clang"] = default_jargon["objective-c"]
    default_jargon["objective-c-gcc"] = default_jargon["objective-c"]
    return default_jargon
