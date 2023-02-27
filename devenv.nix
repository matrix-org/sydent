{ pkgs, ... }:

{
  # https://devenv.sh/packages/
  packages = with pkgs; [
    poetry

    # Native dependencies
    libffi
    libxslt
    openssl

    # For accessing and browsing sqlite3 databases
    sqlite
  ];

  # https://devenv.sh/languages/
  # languages.nix.enable = true;
}
