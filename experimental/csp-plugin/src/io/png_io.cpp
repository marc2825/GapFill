#include "io/png_io.hpp"

#include <cstring>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include "lodepng.h"

namespace gap_assist {

Image loadPng(const std::filesystem::path& path) {
  std::vector<unsigned char> decoded;
  unsigned width = 0;
  unsigned height = 0;
  const unsigned error = lodepng::decode(decoded, width, height, path.string());
  if (error != 0) {
    throw std::runtime_error("Cannot decode PNG " + path.string() + ": " +
                             lodepng_error_text(error));
  }
  if (width > static_cast<unsigned>(std::numeric_limits<int>::max()) ||
      height > static_cast<unsigned>(std::numeric_limits<int>::max())) {
    throw std::overflow_error("PNG dimensions exceed Gap Assist's supported range.");
  }
  Image image(static_cast<int>(width), static_cast<int>(height));
  if (decoded.size() != image.size() * 4) {
    throw std::runtime_error("Decoded PNG has an unexpected RGBA byte count.");
  }
  static_assert(sizeof(Rgba) == 4, "Rgba must remain tightly packed for PNG I/O.");
  std::memcpy(image.pixels().data(), decoded.data(), decoded.size());
  return image;
}

std::vector<std::uint8_t> encodePng(const Image& image) {
  if (image.empty()) throw std::invalid_argument("Cannot encode an empty PNG image.");
  static_assert(sizeof(Rgba) == 4, "Rgba must remain tightly packed for PNG I/O.");
  const auto* bytes =
      reinterpret_cast<const unsigned char*>(image.pixels().data());
  std::vector<unsigned char> encoded;
  const unsigned error = lodepng::encode(encoded, bytes,
                                         static_cast<unsigned>(image.width()),
                                         static_cast<unsigned>(image.height()));
  if (error != 0) {
    throw std::runtime_error("Cannot encode PNG: " +
                             std::string(lodepng_error_text(error)));
  }
  return encoded;
}

void savePng(const std::filesystem::path& path, const Image& image) {
  const auto encoded = encodePng(image);
  if (path.has_parent_path()) std::filesystem::create_directories(path.parent_path());
  std::ofstream output(path, std::ios::binary | std::ios::trunc);
  if (!output) throw std::runtime_error("Cannot write PNG " + path.string());
  output.write(reinterpret_cast<const char*>(encoded.data()),
               static_cast<std::streamsize>(encoded.size()));
  if (!output) throw std::runtime_error("Cannot write PNG " + path.string());
}

SelectionMask loadSelectionPng(const std::filesystem::path& path, int expectedWidth,
                               int expectedHeight) {
  const auto image = loadPng(path);
  if (image.width() != expectedWidth || image.height() != expectedHeight)
    throw std::invalid_argument("Selection PNG dimensions must match the input image.");
  SelectionMask selection(expectedWidth, expectedHeight);
  for (int y = 0; y < expectedHeight; ++y) {
    for (int x = 0; x < expectedWidth; ++x) {
      if (image.at(x, y).a != 0) selection.set(x, y, 255);
    }
  }
  return selection;
}

}  // namespace gap_assist
