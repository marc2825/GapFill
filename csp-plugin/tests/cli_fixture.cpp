#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>

#include "io/png_io.hpp"

namespace ga = gap_assist;

int main(int argc, char** argv) {
  try {
    if (argc != 3) throw std::invalid_argument("Usage: cli_fixture create|verify FILE");
    const std::string command = argv[1];
    const std::filesystem::path path = argv[2];
    if (command == "create" || command == "create-large") {
      const int size = command == "create-large" ? 4096 : 32;
      ga::Image image(size, size, {40, 100, 220, 255});
      image.at(size / 2, size / 2) = {};
      ga::savePng(path, image);
      return 0;
    }
    if (command == "verify") {
      const auto image = ga::loadPng(path);
      if (image.width() != 32 || image.height() != 32)
        throw std::runtime_error("Unexpected correction dimensions.");
      std::size_t opaque = 0;
      for (const auto pixel : image.pixels()) opaque += pixel.a != 0 ? 1U : 0U;
      if (opaque != 1 || image.at(16, 16) != ga::Rgba{40, 100, 220, 255})
        throw std::runtime_error("CLI did not produce the expected correction pixel.");
      return 0;
    }
    throw std::invalid_argument("Unknown fixture command: " + command);
  } catch (const std::exception& error) {
    std::cerr << "Fixture error: " << error.what() << '\n';
    return 1;
  }
}
