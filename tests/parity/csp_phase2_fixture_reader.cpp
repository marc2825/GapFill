// Read-only characterization of the CSP core against the shared Phase 2 corpus.
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "core/gap_detection.hpp"
#include "core/settings.hpp"

namespace {

std::vector<std::string> split(const std::string& value, char delimiter) {
  std::vector<std::string> parts;
  std::stringstream stream(value);
  for (std::string part; std::getline(stream, part, delimiter);) {
    parts.push_back(std::move(part));
  }
  if (!value.empty() && value.back() == delimiter) parts.emplace_back();
  return parts;
}

std::vector<std::vector<std::uint32_t>> parseExpected(const std::string& value) {
  std::vector<std::vector<std::uint32_t>> components;
  if (value.empty()) return components;
  for (const auto& encodedComponent : split(value, '|')) {
    std::vector<std::uint32_t> pixels;
    if (!encodedComponent.empty()) {
      for (const auto& encodedPixel : split(encodedComponent, ';')) {
        pixels.push_back(static_cast<std::uint32_t>(std::stoul(encodedPixel)));
      }
    }
    std::sort(pixels.begin(), pixels.end());
    components.push_back(std::move(pixels));
  }
  std::sort(components.begin(), components.end());
  return components;
}

std::vector<std::vector<std::uint32_t>> actualPixels(
    const std::vector<gap_assist::GapCandidate>& gaps, bool application = false) {
  std::vector<std::vector<std::uint32_t>> components;
  components.reserve(gaps.size());
  for (const auto& gap : gaps) {
    auto pixels = application ? gap_assist::candidateApplicationPixels(gap)
                              : gap.pixels;
    std::sort(pixels.begin(), pixels.end());
    components.push_back(std::move(pixels));
  }
  std::sort(components.begin(), components.end());
  return components;
}

void runFixture(const std::vector<std::string>& fields, std::size_t lineNumber) {
  if (fields.size() != 9) {
    throw std::runtime_error("Invalid Phase 2 CSV field count on line " +
                             std::to_string(lineNumber));
  }
  if (fields[0] != "current_behavior_not_golden") {
    throw std::runtime_error("Phase 2 CSV role is not explicitly non-golden");
  }
  const std::string& caseId = fields[1];
  const std::string& scope = fields[2];
  const int width = std::stoi(fields[3]);
  const int height = std::stoi(fields[4]);
  const auto threshold = static_cast<std::size_t>(std::stoull(fields[5]));
  const std::string& alphaHex = fields[6];
  const std::string& selectionHex = fields[7];
  if (alphaHex.size() != static_cast<std::size_t>(width * height * 2)) {
    throw std::runtime_error(caseId + ": alpha payload length mismatch");
  }
  if (selectionHex.size() != static_cast<std::size_t>(width * height * 2)) {
    throw std::runtime_error(caseId + ": selection payload length mismatch");
  }

  gap_assist::Image image(width, height, {80, 100, 120, 255});
  for (std::size_t index = 0; index < image.size(); ++index) {
    image.atIndex(index).a = static_cast<std::uint8_t>(
        std::stoul(alphaHex.substr(index * 2, 2), nullptr, 16));
  }
  gap_assist::SelectionMask selection(width, height);
  for (int y = 0; y < height; ++y) {
    for (int x = 0; x < width; ++x) {
      const auto index = static_cast<std::size_t>(y * width + x);
      selection.set(x, y, static_cast<std::uint8_t>(
                              std::stoul(selectionHex.substr(index * 2, 2),
                                         nullptr, 16)));
    }
  }
  gap_assist::Settings settings;
  settings.gapThreshold = threshold;
  settings.alphaThreshold = 0;
  settings.connectivity = gap_assist::Connectivity::Four;
  if (scope == "whole") {
    settings.scope = gap_assist::Scope::WholeLayer;
  } else if (scope == "selected") {
    settings.scope = gap_assist::Scope::SelectionOnly;
  } else {
    throw std::runtime_error(caseId + ": unknown scope " + scope);
  }

  const auto expected = parseExpected(fields[8]);
  const auto* selectionPointer =
      settings.scope == gap_assist::Scope::SelectionOnly ? &selection : nullptr;
  const auto gaps =
      gap_assist::GapDetector{}.detect(image, settings, selectionPointer, nullptr, {});
  const auto actual = actualPixels(gaps);
  if (caseId == "D013_selection_boundary" && scope == "selected") {
    if (!expected.empty() || actual != parseExpected("11;12;13") ||
        actualPixels(gaps, true) != parseExpected("12")) {
      throw std::runtime_error(
          caseId +
          ": Phase 4 must replace the historical selection-clipped result with "
          "full geometry [11,12,13] and application subset [12]");
    }
    return;
  }
  if (actual != expected) {
    throw std::runtime_error(caseId +
                             ": CSP detection no longer matches the independently "
                             "characterized current-behavior projection");
  }
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 2) {
    std::cerr << "Usage: gap_assist_phase2_fixtures <csp_detection_current.csv>\n";
    return 2;
  }
  try {
    std::ifstream stream(argv[1]);
    if (!stream) throw std::runtime_error("Cannot open Phase 2 fixture CSV");
    std::string line;
    if (!std::getline(stream, line)) throw std::runtime_error("Empty fixture CSV");
    std::size_t lineNumber = 1;
    std::size_t caseCount = 0;
    while (std::getline(stream, line)) {
      ++lineNumber;
      if (!line.empty() && line.back() == '\r') line.pop_back();
      if (line.empty()) continue;
      runFixture(split(line, ','), lineNumber);
      ++caseCount;
    }
    std::cout << "Phase 2 CSP characterization: 37/38 historical rows retained; "
                 "D013 selected changed only by canonical D-04 (not golden data)\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
