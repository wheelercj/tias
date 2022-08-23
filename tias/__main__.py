from tias.app import main  # use this when packaging and when committing

# from app import main  # use this when testing the unpackaged code

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt")
