from errors import InputError
from textwrap import dedent
from typing import Dict
from typing import Tuple
import sqlite3


async def print_jargon(alias_or_language_name: str, database_file_name: str) -> None:
    """Shows the jargon for a language if it has jargon."""
    try:
        jargon, jargon_key = await load_jargon(
            alias_or_language_name, database_file_name
        )
    except sqlite3.OperationalError:
        jargon, jargon_key = await create_jargon_table(
            alias_or_language_name, database_file_name
        )
    if jargon:
        print(f"\x1b[32mjargon:\x1b[0m\n{jargon}")
        print(f"\x1b[32mjargon key:\x1b[0m {jargon_key}")
    else:
        raise InputError(
            f"No jargon wrapping has been set for the `{alias_or_language_name}`"
            " language"
        )


async def create_jargon_table(
    alias_or_language: str, database_file_name: str
) -> Tuple[str, str]:
    """Creates a sqlite table with default jargon & returns jargon for one language.

    Assumes the table does not exist. Returns empty strings if the language has
    no jargon.

    Returns
    -------
    str
        The language's jargon.
    str
        The language's "jargon key", i.e. something in an expression that, if
        present, means jargon wrapping is not needed.
    """
    default_jargon: Dict[str, Tuple[str, str]] = await get_default_jargon()
    with sqlite3.connect(database_file_name) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE all_jargon (
                id INTEGER PRIMARY KEY,
                alias_or_language_name TEXT NOT NULL,
                jargon TEXT NOT NULL,
                jargon_key TEXT NOT NULL,
                UNIQUE (alias_or_language_name)
            );
            """
        )
        for alias_or_language_name, (jargon, jargon_key) in default_jargon.items():
            await save_jargon(alias_or_language_name, jargon, jargon_key, cursor)
        conn.commit()
    if alias_or_language and alias_or_language in default_jargon:
        return default_jargon[alias_or_language]
    return ("", "")


async def save_jargon(
    alias_or_language_name: str, jargon: str, jargon_key: str, cursor
) -> None:
    """Saves to the database the jargon for an alias or language."""
    cursor.execute(
        """
        INSERT OR IGNORE INTO all_jargon
        (alias_or_language_name, jargon, jargon_key)
        VALUES (?, ?, ?);
        """,
        (alias_or_language_name, jargon, jargon_key),
    )


async def load_jargon(
    alias_or_language_name: str, database_file_name: str
) -> Tuple[str, str]:
    """Gets jargon for an alias or language from the database.

    Returns empty strings if the alias or language has no jargon.

    Returns
    -------
    str
        The language's jargon.
    str
        The language's "jargon key", i.e. something in an expression that, if
        present, means jargon wrapping is not needed.
    """
    try:
        with sqlite3.connect(database_file_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT jargon, jargon_key
                FROM all_jargon
                WHERE alias_or_language_name = ?;
                """,
                [alias_or_language_name],
            )
            records = cursor.fetchall()
            if not records:
                return ("", "")
            jargon, jargon_key = records[0]
            return jargon, jargon_key
    except sqlite3.OperationalError:
        return await create_jargon_table(alias_or_language_name, database_file_name)


async def wrap_jargon(
    expression: str, alias_or_language_name: str, database_file_name: str
) -> str:
    """Wraps code around a given expression if the language has needed jargon.

    Returns the expression unchanged if the language has no jargon or if the
    jargon doesn't appear to be needed.
    """
    jargon, jargon_key = await load_jargon(alias_or_language_name, database_file_name)
    if not jargon:
        return expression
    if jargon_key not in expression:
        return jargon.replace("INSERT_HERE", expression)
    return expression


async def get_default_jargon() -> Dict[str, Tuple[str, str]]:
    default_jargon: Dict[str, Tuple[str, str]] = {
        # keys: alias or language name
        # values:
        #   * the jargon
        #   * the "jargon key"
        "c": (
            dedent(
                """\
                #include <ctype.h>
                #include <math.h>
                #include <stdbool.h>
                #include <stdio.h>
                #include <stdlib.h>
                #include <string.h>
                #include <time.h>

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
