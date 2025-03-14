{pkgs}: {
  deps = [
    pkgs.firefox-esr
    pkgs.geckodriver
    pkgs.fontconfig
    pkgs.freetype
    pkgs.xorg.libXrender
    pkgs.gdk-pixbuf
    pkgs.gtk3
    pkgs.xorg.libxcb
    pkgs.mesa
    pkgs.expat
    pkgs.alsa-lib
    pkgs.udev
    pkgs.libxkbcommon
    pkgs.xorg.libXfixes
    pkgs.xorg.libXdamage
    pkgs.xorg.libXcomposite
    pkgs.cairo
    pkgs.pango
    pkgs.atk
    pkgs.dbus
    pkgs.nspr
    pkgs.nss
    pkgs.playwright-driver
    pkgs.gitFull
    pkgs.postgresql
    pkgs.openssl
  ];
}
