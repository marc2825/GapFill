#include <iostream>

int main() {
  std::cout
      << "Gap Assist CSP host contract v1\n\n"
      << "Required for the native adapter:\n"
      << "  [ ] read active raster RGBA pixels\n"
      << "  [ ] present one review dialog\n"
      << "  [ ] report progress and cancellation\n"
      << "  [ ] create a correction raster layer (preferred)\n"
      << "  [ ] read the selection mask (optional)\n"
      << "  [ ] overwrite pixels with one Undo transaction (optional)\n\n"
      << "Unverified capabilities must remain disabled. No CELSYS SDK files "
         "were inspected by this probe.\n";
  return 0;
}
