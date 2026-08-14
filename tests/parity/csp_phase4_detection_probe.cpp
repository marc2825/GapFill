#include <algorithm>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

#include "core/gap_detection.hpp"
#include "core/settings.hpp"

namespace ga = gap_assist;

namespace {

void fillMask(ga::BinaryMask& mask, const std::string& encoded) {
  if (encoded.size() != mask.size())
    throw std::invalid_argument("binary mask payload length mismatch");
  for (int y = 0; y < mask.height(); ++y) {
    for (int x = 0; x < mask.width(); ++x) {
      const char value = encoded[static_cast<std::size_t>(y * mask.width() + x)];
      if (value != '0' && value != '1')
        throw std::invalid_argument("binary masks use only 0 and 1");
      mask.set(x, y, value == '1');
    }
  }
}

template <typename Values>
void printValues(const Values& values) {
  for (std::size_t index = 0; index < values.size(); ++index) {
    if (index != 0) std::cout << ',';
    std::cout << values[index];
  }
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 8) {
    std::cerr << "usage: probe WIDTH HEIGHT THRESHOLD COLORING LINE GUIDE SELECTION\n";
    return 2;
  }
  try {
    const int width = std::stoi(argv[1]);
    const int height = std::stoi(argv[2]);
    ga::DetectionGeometry geometry(width, height);
    fillMask(geometry.coloringGap, argv[4]);
    fillMask(geometry.lineBoundary, argv[5]);
    fillMask(geometry.guideBoundary, argv[6]);

    ga::SelectionMask selection(width, height);
    const bool selected = std::string(argv[7]) != "-";
    if (selected) {
      const std::string encoded = argv[7];
      if (encoded.size() != selection.values().size())
        throw std::invalid_argument("selection payload length mismatch");
      for (int y = 0; y < height; ++y)
        for (int x = 0; x < width; ++x)
          selection.set(x, y, encoded[static_cast<std::size_t>(y * width + x)] == '1'
                                  ? 255
                                  : 0);
    }

    ga::Settings settings;
    settings.gapThreshold = static_cast<std::size_t>(std::stoull(argv[3]));
    settings.scope = selected ? ga::Scope::SelectionOnly : ga::Scope::WholeLayer;
    settings.connectivity = ga::Connectivity::Four;
    const auto gaps = ga::GapDetector{}.detect(
        geometry, settings, selected ? &selection : nullptr);
    for (const auto& gap : gaps) {
      std::cout << gap.id << '|';
      printValues(gap.pixels);
      std::cout << '|';
      printValues(ga::candidateApplicationPixels(gap));
      std::cout << '|' << gap.bbox.x << ',' << gap.bbox.y << ',' << gap.bbox.width << ','
                << gap.bbox.height << '|' << static_cast<int>(gap.centroid.x) << ','
                << static_cast<int>(gap.centroid.y) << '\n';
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
