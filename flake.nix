{
  description = "docsys — the engine's own development shell";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";

  outputs =
    { self, nixpkgs }:
    let
      # CI runs on linux; the maintainer is on x86_64-darwin.
      systems = [
        "x86_64-darwin"
        "aarch64-darwin"
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f (import nixpkgs { inherit system; }));
    in
    {
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          # The engine pins its own development tools; an adopter installs the
          # package and needs none of them. markdownlint-cli2's version is part of
          # the contract with the sentence-per-line rule (tools/markdownlint).
          packages = [
            pkgs.python3
            pkgs.uv # installs what uv.lock pins, into a .venv built on this interpreter
            pkgs.nodejs
            pkgs.markdownlint-cli2
            pkgs.git
          ];

          shellHook = ''
            export DOCSYS_DEVSHELL=1
            export UV_PYTHON=${pkgs.python3}/bin/python3
            export UV_PYTHON_DOWNLOADS=never
          '';
        };
      });

      formatter = forAllSystems (pkgs: pkgs.nixfmt-rfc-style);
    };
}
