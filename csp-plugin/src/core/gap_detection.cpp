#include "core/gap_detection.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <limits>
#include <stdexcept>

namespace gap_assist {
namespace {

constexpr std::array<Point, 4> kCardinal{{{-1, 0}, {1, 0}, {0, -1}, {0, 1}}};
constexpr std::array<Point, 4> kDiagonal{{{-1, -1}, {1, -1}, {-1, 1}, {1, 1}}};

bool inScope(const SelectionMask* selection, const Settings& settings, int x, int y,
             int width, int height) {
  if (x < 0 || y < 0 || x >= width || y >= height) return false;
  return settings.scope != Scope::SelectionOnly ||
         (selection != nullptr && selection->selected(x, y));
}

}  // namespace

std::vector<GapCandidate> GapDetector::detect(
    const Image& image, const Settings& settings, const SelectionMask* selection,
    const std::atomic_bool* cancelled, const ProgressCallback& progress) const {
  if (image.empty() || settings.gapThreshold == 0) return {};
  if (settings.scope == Scope::SelectionOnly &&
      (selection == nullptr || selection->width() != image.width() ||
       selection->height() != image.height())) {
    throw std::invalid_argument(
        "Selection-only scope requires a mask matching the image dimensions.");
  }

  const int width = image.width();
  const int height = image.height();
  std::vector<std::uint8_t> visited(image.size(), 0);
  std::vector<std::uint32_t> work;
  work.reserve(std::min(image.size(), settings.gapThreshold));
  std::vector<GapCandidate> gaps;

  const auto isCandidate = [&](int x, int y) {
    return inScope(selection, settings, x, y, width, height) &&
           image.at(x, y).a <= settings.alphaThreshold;
  };

  for (int y = 0; y < height; ++y) {
    if (cancelled != nullptr && cancelled->load())
      throw std::runtime_error("Gap detection cancelled.");
    for (int x = 0; x < width; ++x) {
      const auto seed = static_cast<std::size_t>(y) * static_cast<std::size_t>(width) +
                        static_cast<std::size_t>(x);
      if (visited[seed] != 0 || !isCandidate(x, y)) continue;

      work.clear();
      work.push_back(static_cast<std::uint32_t>(seed));
      visited[seed] = 1;
      std::vector<std::uint32_t> retainedPixels;
      retainedPixels.reserve(std::min(image.size(), settings.gapThreshold));
      std::size_t cursor = 0;
      std::size_t area = 0;
      std::uint64_t sumX = 0;
      std::uint64_t sumY = 0;
      int minX = std::numeric_limits<int>::max();
      int minY = std::numeric_limits<int>::max();
      int maxX = -1;
      int maxY = -1;
      bool open = false;

      while (cursor < work.size()) {
        if (cancelled != nullptr && (cursor & 0xffffU) == 0 && cancelled->load())
          throw std::runtime_error("Gap detection cancelled.");
        const auto flat = work[cursor++];
        const int currentX = static_cast<int>(flat % static_cast<std::uint32_t>(width));
        const int currentY = static_cast<int>(flat / static_cast<std::uint32_t>(width));
        ++area;
        if (retainedPixels.size() < settings.gapThreshold) retainedPixels.push_back(flat);
        sumX += static_cast<std::uint64_t>(currentX);
        sumY += static_cast<std::uint64_t>(currentY);
        minX = std::min(minX, currentX);
        minY = std::min(minY, currentY);
        maxX = std::max(maxX, currentX);
        maxY = std::max(maxY, currentY);
        if (currentX == 0 || currentY == 0 || currentX + 1 == width ||
            currentY + 1 == height) {
          open = true;
        }
        if (settings.scope == Scope::SelectionOnly) {
          for (const auto offset : kCardinal) {
            if (!inScope(selection, settings, currentX + offset.x,
                         currentY + offset.y, width, height)) {
              open = true;
            }
          }
          if (settings.connectivity == Connectivity::Eight) {
            for (const auto offset : kDiagonal) {
              if (!inScope(selection, settings, currentX + offset.x,
                           currentY + offset.y, width, height)) {
                open = true;
              }
            }
          }
        }

        const auto enqueue = [&](int nextX, int nextY) {
          if (!isCandidate(nextX, nextY)) return;
          const auto next = static_cast<std::size_t>(nextY) *
                                static_cast<std::size_t>(width) +
                            static_cast<std::size_t>(nextX);
          if (visited[next] != 0) return;
          visited[next] = 1;
          work.push_back(static_cast<std::uint32_t>(next));
        };
        for (const auto offset : kCardinal)
          enqueue(currentX + offset.x, currentY + offset.y);
        if (settings.connectivity == Connectivity::Eight) {
          for (const auto offset : kDiagonal)
            enqueue(currentX + offset.x, currentY + offset.y);
        }
      }

      if (open || area > settings.gapThreshold) continue;
      const double areaAsDouble = static_cast<double>(area);
      GapCandidate gap;
      gap.id = static_cast<int>(gaps.size());
      gap.pixels = std::move(retainedPixels);
      gap.area = area;
      gap.bbox = {minX, minY, maxX - minX + 1, maxY - minY + 1};
      gap.centroid = {static_cast<double>(sumX) / areaAsDouble,
                      static_cast<double>(sumY) / areaAsDouble};
      gaps.push_back(std::move(gap));
    }
    if (progress && (y % 64 == 0 || y + 1 == height)) progress(y + 1, height);
  }

  return gaps;
}

}  // namespace gap_assist
