{ pkgs }: {
  deps = [
    pkgs.python311
    pkgs.postgresql
    pkgs.gdal
    pkgs.geos
    pkgs.proj
  ];
}
