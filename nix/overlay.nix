# nix/overlay.nix — Nixpkgs overlay exposing pkgs.hermes-agent.
#
# Stable Nix (no flakes):
#   nixpkgs.overlays = [ (import ./nix/overlay.nix { }) ];
# Build inputs default to nix/inputs.nix (which reads flake.lock), so a plain
# Nix consumer needs nothing but this repo.
#
# The flake passes its own locked inputs explicitly, so existing flake users get
# byte-identical derivations.
{
  uv2nix ? null,
  pyproject-nix ? null,
  pyproject-build-systems ? null,
  # npm-lockfile-fix has no classic entrypoint (flake-only). Pass the flake
  # input to build the node sub-packages (tui/web/desktop); null is fine for the
  # core Python package and the NixOS module default.
  npm-lockfile-fix ? null,
  rev ? null,
}:
final: _prev:
let
  stable = import ./inputs.nix { inherit (final) lib; };
in
{
  hermes-agent = final.callPackage ./hermes-agent.nix {
    uv2nix = if uv2nix != null then uv2nix else stable.uv2nix;
    pyproject-nix = if pyproject-nix != null then pyproject-nix else stable.pyproject-nix;
    pyproject-build-systems =
      if pyproject-build-systems != null then pyproject-build-systems else stable.pyproject-build-systems;
    npm-lockfile-fix =
      if npm-lockfile-fix == null then null
      else npm-lockfile-fix.packages.${final.stdenv.hostPlatform.system}.default;
    inherit rev;
  };
}
